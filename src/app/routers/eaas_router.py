'''
Experimentation as a Service (EaaS) API Specification
'''
from __future__ import annotations
from typing import Optional, Union, Any
from uuid import UUID
import httpx
from fastapi import APIRouter, Path, HTTPException, Header, Depends, status  #, Query
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from app.models.eaas_models import (
    AppPkgInfo,
    CreateInstanceApplicationRequest,
    ProblemDetails,
    StopInstanceApplicationRequest,
    # AppDescriptor,
    AppInstanceInstantiationState,
    # AppPackagesGetResponse,
    # CreateAppPkgInfoRequest,
    # CreateExperimentDescriptorInfoRequest,
    # CreateExperimentRequest,
    # ExperimentDescriptorInfo,
    # ExperimentInstance,
    # InstantiateExperimentRequest,
    # TerminateExperimentRequest,
)
import app.models.camara_models as camara
from app.api_clients import get_camara_client, get_app_repo_client
from app.utils.logger import logger
from app.config import config
from app.utils.descriptor_builders import (build_app_descriptor_from_repo_payload)
from app.utils.eaas2camara_builder import build_camara_app_manifest

router = APIRouter()


# ---------------------
# /application_onboarding
# ---------------------
@router.post(
    '/application_onboarding',
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Application onboarded successfully",
            "content": {
                "application/json": {
                    "example": "generated-app-id-123"
                }
            },
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [{
                            "loc": ["body", 0],
                            "msg": "Invalid format",
                            "type": "value_error"
                        }]
                    }
                },
            },
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "CAMARA error 500: unexpected response"
                    }
                },
            },
        },
    },
    tags=['Southbound Plugin'],
)
def post_application_onboarding(
    body: AppPkgInfo,
    x_correlator: Optional[str] = Header(None, alias="x-correlator"),
    camara_client: httpx.Client = Depends(get_camara_client),
    app_repo_client: httpx.Client = Depends(get_app_repo_client)
) -> JSONResponse:
    """
    Onboard the application by transforming AppPkgInfo into AppManifest and submitting to CAMARA.
    """
    if config.DEBUG:
        logger.info(f"In POST onboard received Body: {body}")
    try:
        # [POST] body is of type AppPkgInfo (see eaas_models) and includes information about
        #   AppDescriptor and AppArtifacts ... and more
        # We need to convert to CAMARA AppManifest (see camara_models)
        # A bit of confusion:
        #   Some fields are included in both AppPkgInfo and AppDescriptor
        #   Do we need Artifacts ?
        #   Information such as networking properties, env arguments could be included in userDefinedData?
        # Step 1: Extract App Package ID
        app_package_id = body.id  # [body.id == AppPackageInfoId]
        if config.DEBUG:
            logger.info(f"Received package id: {app_package_id}")
        # Step 2: Get app descriptor from EaaS Application Repository with AppPkgId
        # Check EaaSModule-Application-Onboarding step 8
        # Response is of type AppDescriptor from EaaS Models
        
        try:
            response = app_repo_client.get(
                f"/app_packages/{app_package_id}/app_descriptor"
            )
            if config.DEBUG:
                logger.info(f"Actual request URL: {response.request.url}")
                logger.info(f"App repo status: {response.status_code}")
                logger.info(f"App repo body: {response.text}")
            response.raise_for_status()
        except httpx.RequestError as exc:
            logger.exception("Error while requesting app repo")
            raise HTTPException(
                status_code=502,
                detail=f"Error connecting to app repo: {exc}",
            ) from exc
        except httpx.HTTPStatusError as exc:
            logger.exception("Bad status from app repo")
            raise HTTPException(
                status_code=502,
                detail=f"App repo returned {exc.response.status_code}",
            ) from exc


        # if config.DEBUG:
        #     logger.info(f"Response from Application repository: {response.status_code} \n  {response.text} \n {response.json()}")
        response.raise_for_status()
        # FIXME: this needs work
        import json
        if config.DEBUG:
            pretty = json.dumps(response.json(), indent=2, sort_keys=True)
            logger.info(f"BEFORE App descriptor JSON:\n{pretty}")
        app_descriptor = build_app_descriptor_from_repo_payload(response.json())
        if config.DEBUG:
            raw_json = app_descriptor.json()              # compact JSON string
            pretty = json.dumps(json.loads(raw_json), indent=2, sort_keys=True)
            logger.info(f"##### Application descriptor (AppAppDescriptor) ###### : {pretty}")

        # FIXME: Check for artifacts
        # Step 3: Check for application artifacts endpoint
        # Example: if not check_artifacts_available(app_descriptor): raise SomeError()

        # Step 4: Extract and map AppDescriptor and optional [TOSCA??] artifacts to CAMARA AppManifest
        # We need something like: app_manifest = map_to_camara_manifest(app_descriptor, app_artifacts)
        # for now inline, but needs to move
        # app_manifest = camara.AppManifest(
        #     appId='OnBoadrdAppId',
        #     name=app_descriptor.appProductName,
        #     appProvider=app_descriptor.appProvider,
        #     version=app_descriptor.appSoftwareVersion,
        #     packageType="CONTAINER",
        #     appRepo=camara.AppRepo(
        #         type='', imagePath='', userName='',
        #         credentials=''),  # Get them from AppDescriptor ??
        #     requiredResources=camara.RequiredResources(),  # FIXME
        #     componentSpec=[camara.ComponentSpecItem()]  # FIXME
        # )
        # if config.DEBUG:
        #     logger.info(f"app manifest for CAMARA: app_manifest={app_manifest}")

        app_manifest = build_camara_app_manifest(app_descriptor)

        if config.DEBUG:
            pretty_manifest = json.dumps(json.loads(app_manifest.json()), indent=2)
            logger.info(f"##### CAMARA AppManifest ###### :\n {pretty_manifest}" )

        # Step 5: POST to CAMARA /apps
        headers = {}
        if x_correlator:
            headers["x-correlator"] = x_correlator

        response = camara_client.post(
            url="/apps/",  # relative to base_url set in client
            json=app_manifest.model_dump(mode="json", exclude_unset=True),
            headers=headers)  
        if config.DEBUG:
            logger.info(f"Response from CAMARA API: {response.status_code} - {response.text} - {response.json()}")

        if response.status_code == 201:
            logger.info(f"CAMARA succss response: {response.text}")
            camara_response = camara.SubmittedApp(**response.json())
            if config.DEBUG:
                logger.info(f"camara to pydantic:  {camara_response}")
            app_id = str(camara_response.appId.root
                         ) if camara_response.appId else "unknown-app-id"
            return JSONResponse(status_code=status.HTTP_201_CREATED,
                                content=app_id)

        try:
            logger.info(f"CAMARA error response: {response.text}")
            error_info = camara.ErrorInfo(**response.json())
            error_detail = error_info.message
        except Exception:
            error_detail = response.text

        raise HTTPException(
            status_code=500,
            detail=f"CAMARA error {response.status_code}: {error_detail}")

    except ValidationError as e:
        logger.error(f"##################### \n Error parsing AppDescriptor: {e.json()}\n")
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=e.errors()) from e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


# ---------------------
# /create_application_instance
# ---------------------
@router.post(
    '/create_application_instance',
    response_model=None,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "description": "Application instance created",
            "content": {
                "application/json": {
                    "example": "generated-instance-id-456"
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [{
                            "loc": ["body", 0],
                            "msg": "Invalid format",
                            "type": "value_error"
                        }]
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "CAMARA error 500: unexpected failure"
                    }
                }
            }
        }
    },
    tags=['Southbound Plugin'],
)
def post_create_application_instance(
    body: CreateInstanceApplicationRequest,
    x_correlator: Optional[str] = Header(None, alias="x-correlator"),
    camara_client: httpx.Client = Depends(get_camara_client),
) -> JSONResponse:
    """
    Create (and start) an application's instance
    """
    try:
        # Step 1: Extract required data
        raw_app_onboarding_id = body.appOnboardingId
        app_onboarding_id = raw_app_onboarding_id.strip().strip('"')
        additional_params = body.additionalParams or {}
        if config.DEBUG:
            logger.info("App onboarding id (repr): {!r}", app_onboarding_id)
            logger.info("Length: {}", len(app_onboarding_id) if app_onboarding_id is not None else None)
            logger.info("Type: {}", type(app_onboarding_id))

        # Simulate resolving metadata
        logger.info("starting ....")
        app_id = camara.AppId(UUID(app_onboarding_id))
        logger.info("app_id")
        app_name = camara.AppInstanceName(additional_params.get("appInstanceName", "NameMissingApp"))
        logger.info("app_name")
        edge_cloud_zone_id = additional_params.get("edgeCloudZoneId", "urn:ngsi-ld:Domain:ncsrd01")
        logger.info("zone_id")
        # k8s_ref = additional_params.get("kubernetesClusterRef")

        camara_request = camara.AppinstancesPostRequest(
            name=app_name,
            appId=app_id,
            edgeCloudZoneId=edge_cloud_zone_id)
            # kubernetesClusterRef=k8s_ref)
        logger.info(f"camara_request raw: {camara_request}")
        logger.info(f'camara_request body: {camara_request.model_dump(mode="json", exclude_unset=True)}')
        # Step 2: Call CAMARA /apps/instances
        headers = {}
        if x_correlator:
            headers["x-correlator"] = x_correlator

        response = camara_client.post(
            url="/appinstances",
            json=camara_request.model_dump(mode="json", exclude_unset=True),
            headers=headers,
        )

        if response.status_code in (201, 202):
            camara_response = response.json()
            logger.info(f"CAMARA Response: {camara_response}")
            instance_id = camara_response.get("appDeploymentId").strip().strip('"')
            logger.info(f"App deployment Id: {instance_id}")
            return JSONResponse(status_code=status.HTTP_201_CREATED,
                                content=instance_id)

        try:
            error_info = camara.ErrorInfo(**response.json())
            error_detail = error_info.detail
            logger.info("camara error")
        except Exception:
            error_detail = response.text
            logger.info("set up error")

        raise HTTPException(
            status_code=500,
            detail=f"CAMARA error {response.status_code}: {error_detail}")

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=e.errors()) from e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex


# ---------------------
# /stop_application_instance
# ---------------------
@router.post(
    '/stop_application_instance',
    response_model=None,
    status_code=status.HTTP_200_OK,
    responses={
        200: {
            "description": "Application instance stop accepted",
            "content": {
                "application/json": {
                    "example": "Application instance stop accepted"
                }
            }
        },
        422: {
            "description": "Validation error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": [{
                            "loc": ["body", 0],
                            "msg": "Invalid format",
                            "type": "value_error"
                        }]
                    }
                }
            }
        },
        500: {
            "description": "Internal Server Error",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "CAMARA error 503: service unavailable"
                    }
                }
            }
        }
    },
    tags=['Southbound Plugin'],
)
def post_stop_application_instance(
    body: StopInstanceApplicationRequest,
    x_correlator: Optional[str] = Header(None, alias="x-correlator"),
    camara_client: httpx.Client = Depends(get_camara_client),
) -> JSONResponse:
    """
    Stop an application's instance
    """
    try:
        # Step 1: Parse and validate appInstanceId
        try:
            app_instance_id = UUID(body.appInstanceId)
        except ValueError as e:
            raise HTTPException(status_code=422,
                                detail=[{
                                    "loc": ["body", "appInstanceId"],
                                    "msg": str(e),
                                    "type": "value_error.uuid"
                                }]) from e

        # Step 2: Send DELETE request to CAMARA
        headers = {}
        if x_correlator:
            headers["x-correlator"] = x_correlator

        response = camara_client.delete(
            url=f"/appinstances/{app_instance_id}", headers=headers)

        if response.status_code == 202:
            return JSONResponse(status_code=status.HTTP_200_OK,
                                content="Application instance stop accepted")

        try:
            error_info = camara.ErrorInfo(**response.json())
            error_detail = error_info.detail
        except Exception:
            error_detail = response.text

        raise HTTPException(
            status_code=500,
            detail=f"CAMARA error {response.status_code}: {error_detail}")

    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail=e.errors()) from e
    except Exception as ex:
        raise HTTPException(status_code=500, detail=str(ex)) from ex



# --------------------- STATUS Update -------- #

def map_camara_status_to_state(raw_status: str) -> AppInstanceInstantiationState:
    '''
    Docstring for map_camara_status_to_state
    
    :param raw_status: CAMARA instantiation state string
    :type raw_status: str
    :return: Mapped AppInstanceInstantiationState enum value
    :rtype: AppInstanceInstantiationState
    ''' 
    if raw_status is None:
        # Caller decides whether to treat as 502 or FAILED
        raise ValueError("Missing status")

    s = str(raw_status).strip().upper()

    # IMPORTANT: Replace/extend these values with the exact ones you observe from CAMARA.
    INSTANTIATED = {"INSTANTIATED", "RUNNING", "READY", "STARTED", "ACTIVE"}
    INSTANTIATING = {"INSTANTIATING", "CREATING", "PROVISIONING", "DEPLOYING", "STARTING", "PENDING"}
    NOT_INSTANTIATED = {"NOT_INSTANTIATED", "TERMINATED", "STOPPED", "DELETED", "REMOVED", "INACTIVE"}
    FAILED = {"FAILED", "ERROR", "FAILURE"}

    if s in INSTANTIATED:
        logger.info("in INSTANTIATED")
        return AppInstanceInstantiationState.INSTANTIATED
    if s in INSTANTIATING:
        logger.info("in INSTANTIATING")
        return AppInstanceInstantiationState.INSTANTIATING
    if s in NOT_INSTANTIATED:
        logger.info("NOT INTANTIATED")
        return AppInstanceInstantiationState.NOT_INSTANTIATED
    if s in FAILED:
        logger.info("in FAILED")
        return AppInstanceInstantiationState.FAILED

    # If CAMARA returns an unexpected status, treat as integration error (502)
    raise ValueError("Unsupported status from CAMARA: {raw_status}")







@router.get(
    "/{instanceId}/state",
    response_model=str,  # success: state string/enum value
    responses={
        200: {"description": "Application instance state retrieved"},
        404: {"model": ProblemDetails, "description": "Instance not found"},
        422: {"model": ProblemDetails, "description": "Invalid instanceId"},
        401: {"model": ProblemDetails, "description": "Unauthorized"},
        403: {"model": ProblemDetails, "description": "Forbidden"},
        502: {"model": ProblemDetails, "description": "Bad Gateway"},
        503: {"model": ProblemDetails, "description": "Service Unavailable"},
        500: {"model": ProblemDetails, "description": "Internal Server Error"},
    },
    tags=["Southbound Plugin"],
)
def get_instance_id_state_ws(
    instance_id: str = Path(..., alias="instanceId"),
    x_correlator: Optional[str] = Header(None, alias="x-correlator"),
    camara_client: httpx.Client = Depends(get_camara_client),
) -> Union[str, JSONResponse]:
    """
    Fetch the status of a specific deployment/instance by instanceId.
    Calls CAMARA GET /deployments?appDeploymentId=<uuid>.
    Returns a mapped AppInstanceInstantiationState string on success.
    """
    logger.info("IN GET /%s/state", instance_id)

    # Parse UUID
    try:
        app_instance_uuid = UUID(instance_id.strip().strip('"'))
        logger.info(f"Instance clear: {app_instance_uuid}")
    except ValueError:
        problem = ProblemDetails(
            type="about:blank",
            title="Invalid UUID",
            status=422,
            detail=f"Invalid instanceId format: {instance_id}",
        )
        return JSONResponse(status_code=422, content=problem.model_dump())

    # Propagate correlator (optional)
    headers = {}
    if x_correlator:
        headers["x-correlator"] = x_correlator

    try:
        # IMPORTANT: you said the CAMARA endpoint is /appinstances (top-level list)
        camara_resp = camara_client.get(
            url="/appinstances",
            params={"appDeploymentId": str(app_instance_uuid)},
            headers=headers,
        )

        # Non-200: return as ProblemDetails
        if camara_resp.status_code != 200:
            title = "Client error" if 400 <= camara_resp.status_code < 500 else "Server error"
            problem = ProblemDetails(
                type="about:blank",
                title=title,
                status=camara_resp.status_code,
                detail=f"CAMARA response: {camara_resp.text}",
            )
            return JSONResponse(status_code=camara_resp.status_code, content=problem.model_dump())

        # 200 OK: expect a top-level list
        payload: Any = camara_resp.json()
        if not isinstance(payload, list):
            problem = ProblemDetails(
                type="about:blank",
                title="Bad Gateway",
                status=502,
                detail="CAMARA returned unexpected payload shape; expected a JSON array.",
                additionalAttribute={"camaraResponseSnippet": camara_resp.text[:500]},
            )
            return JSONResponse(status_code=502, content=problem.model_dump())

        if not payload:
            problem = ProblemDetails(
                type="about:blank",
                title="Not Found",
                status=404,
                detail=f"Deployment with ID {instance_id} not found",
            )
            return JSONResponse(status_code=404, content=problem.model_dump())

        deployment = payload[0]

        # **CHECK**: adjust the field name based on your AppDeploymentInfo schema
        raw_status = deployment.get("status")
        logger.info("Raw status from CAMARA deployment: %s", raw_status)

        try:
            mapped_state = map_camara_status_to_state(raw_status)
            logger.info("Mapped state from CAMARA deployment: %s", mapped_state)
            return mapped_state
        except ValueError as ve:
            problem = ProblemDetails(
                type="about:blank",
                title="Bad Gateway",
                status=502,
                detail=str(ve),
                additionalAttribute={
                    "camaraStatus": raw_status,
                    "camaraResponseSnippet": camara_resp.text[:500],
                },
            )
            return JSONResponse(status_code=502, content=problem.model_dump())

    except httpx.TimeoutException as ex:
        problem = ProblemDetails(
            type="about:blank",
            title="Service Unavailable",
            status=503,
            detail=f"Timeout calling CAMARA: {ex}",
        )
        logger.info("Timeout calling CAMARA: %s", ex)
        return JSONResponse(status_code=503, content=problem.model_dump())

    except Exception as ex:
        problem = ProblemDetails(
            type="about:blank",
            title="Internal Server Error",
            status=500,
            detail=str(ex),
        )
        logger.info(f"All other reasons: {ex}")
        return JSONResponse(status_code=500, content=problem.model_dump())









# @router.get(
#     '/{instanceId}/state',
#     response_model=None,
#     responses={
#         "200": {
#             "description": "Application instance state retrieved",
#         },
#         "4XX": {
#             "model": ProblemDetails,
#             "description": "Client error"
#         },
#         "5XX": {
#             "model": ProblemDetails,
#             "description": "Server error"
#         },
#     },
#     tags=['Southbound Plugin'],
# )
# def get_instance_id_state_ws(
#     instance_id: str = Path(..., alias='instanceId'),
#     x_correlator: Optional[str] = Header(None, alias="x-correlator"),
#     camara_client: httpx.Client = Depends(get_camara_client),
# ) -> Optional[ProblemDetails]:
#     """
#     Fetch the status of a specific application instance by instanceId
#     Returns a JSON string enum per AppInstanceInstantiationState.
#     """
#     logger.info(f"IN GET /{instance_id}/state")

#     try:
#         app_instance_uuid = UUID(instance_id.strip().strip('"'))
#         logger.info(f"Instance clear: {app_instance_uuid}")
#     except ValueError:
#         logger.info(f"Value Error for instance id: {instance_id}")
#         return ProblemDetails(
#             type="about:blank",
#             title="Invalid UUID",
#             status=422,
#             detail=f"Invalid instanceId format: {instance_id}",
#         )

#     headers = {}
#     if x_correlator:
#         headers["x-correlator"] = x_correlator
#     logger.info("Ready to try CAMARA call")
#     try:
#         response = camara_client.get(
#             url="/appinstances",
#             params={"appDeploymentId": str(app_instance_uuid)},
#             headers=headers)

#         # 200 OK from CAMARA
#         if response.status_code == 200:
#             payload = response.json()
#             logger.info(f"Response payload: {payload}")
#             instances = payload.get("instances", [])
#             logger.info(f"Instances: {instances}")

#             if not instances:
#                 logger.info("No instances found.")
#                 return ProblemDetails(
#                     type="about:blank",
#                     title="Not Found",
#                     status=404,
#                     detail=f"App instance with ID {instance_id} not found")
        
#         raw_status = instances[0].get("status")
#         logger.info(f"Raw status from CAMARA: {raw_status}")

#         try:
#             v = map_camara_status_to_state(raw_status)
#             logger.info(f"Mapped instantce status: {v}")
#             return v
#         except ValueError as ve:
#             # CAMARA returned a status API does not understand
#             return ProblemDetails(
#                 status=502,
#                 title="Bad Gateway",
#                 detail=str(ve),
#                 additionalAttribute={
#                     "camaraStatus": raw_status,
#                     "camaraResponseSnippet": response.text[:500],
#                 },
#             )

#         # 4XX errors from CAMARA
#         if 400 <= response.status_code < 500:
#             try:
#                 error = ProblemDetails(
#                     type="about:blank",
#                     title="Not Found",
#                     status=response.status_code,
#                     detail=f"CAMARA response: {response.text}")
#             except Exception:
#                 error = ProblemDetails(status=response.status_code,
#                                        title="Client error",
#                                        detail=response.text)
#             return error

#         # 5XX errors from CAMARA
#         try:
#             error = ProblemDetails(type="about:blank",
#                                    title="Not Found",
#                                    status=response.status_code,
#                                    detail=f"CAMARA response: {response.text}")
#         except Exception:
#             error = ProblemDetails(status=response.status_code,
#                                    title="Server error",
#                                    detail=response.text)
#         return error

#     except Exception as ex:
#         return ProblemDetails(type="about:blank",
#                               title="Internal Server Error",
#                               status=500,
#                               detail=str(ex))


############################################################################################
# All other EaaS APIs (following this point) not to be implemented per site
############
# @router.get(
#     '/app_packages',
#     response_model=AppPackagesGetResponse,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def get_app_packages(
#     show_public: Optional[bool] = Query(None, alias='showPublic')
# ) -> Union[AppPackagesGetResponse, ProblemDetails]:
#     """
#     Query Application packages information.
#     """
#     pass

# @router.post(
#     '/app_packages',
#     response_model=None,
#     responses={
#         '201': {'model': AppPkgInfo},
#         '4XX': {'model': ProblemDetails},
#         '5XX': {'model': ProblemDetails},
#     },
#     tags=['EaaS Application Repository'],
# )
# def post_app_packages(
#     body: CreateAppPkgInfoRequest,
# ) -> Optional[Union[AppPkgInfo, ProblemDetails]]:
#     """
#     Create Application Package Info
#     """
#     pass

# @router.get(
#     '/app_packages/{appPkgId}',
#     response_model=AppPkgInfo,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def get_app_packages_app_pkg_id(
#     app_pkg_id: str = Path(..., alias='appPkgId')
# ) -> Union[AppPkgInfo, ProblemDetails]:
#     """
#     Fetch Application Package Info
#     """
#     pass

# @router.delete(
#     '/app_packages/{appPkgId}',
#     response_model=AppPkgInfo,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def delete_app_packages_app_pkg_id(
#     app_pkg_id: str = Path(..., alias='appPkgId')
# ) -> Union[AppPkgInfo, ProblemDetails]:
#     """
#     Delete Application Package Info
#     """
#     pass

# @router.get(
#     '/app_packages/{appPkgId}/app_descriptor',
#     response_model=AppDescriptor,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def get_app_packages_app_pkg_id_app_descriptor(
#     app_pkg_id: str = Path(..., alias='appPkgId')
# ) -> Union[AppDescriptor, ProblemDetails]:
#     """
#     Read Application Descriptor of an on-boarded Application package.
#     """
#     pass

# @router.get(
#     '/app_packages/{appPkgId}/artifacts/{artifactPath}',
#     response_model=bytes,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def get_app_packages_app_pkg_id_artifacts_artifact_path(
#     app_pkg_id: str = Path(..., alias='appPkgId'),
#     artifact_path: str = Path(..., alias='artifactPath'),
# ) -> Union[bytes, ProblemDetails]:
#     """
#     Fetch Application Package Artifact
#     """
#     pass

# @router.get(
#     '/app_packages/{appPkgId}/manifest',
#     response_model=str,
#     tags=['EaaS Application Repository'],
# )
# def get_app_packages_app_pkg_id_manifest(
#     app_pkg_id: str = Path(..., alias='appPkgId')
# ) -> str:
#     """
#     Read the manifest of an on-boarded Application package
#     """
#     pass

# @router.put(
#     '/app_packages/{appPkgId}/package_content',
#     response_model=None,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def put_app_packages_app_pkg_id_package_content(
#     app_pkg_id: str = Path(..., alias='appPkgId')
# ) -> Optional[ProblemDetails]:
#     """
#     Upload Application Package
#     """
#     pass

# @router.put(
#     '/app_packages/{appPkgId}/usage/{requestId}',
#     response_model=None,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def put_app_packages_app_pkg_id_usage_request_id(
#     app_pkg_id: str = Path(..., alias='appPkgId'),
#     request_id: str = Path(..., alias='requestId'),
# ) -> Optional[ProblemDetails]:
#     """
#     Request to use the AppPkgId
#     """
#     pass

# @router.delete(
#     '/app_packages/{appPkgId}/usage/{requestId}',
#     response_model=None,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def delete_app_packages_app_pkg_id_usage_request_id(
#     app_pkg_id: str = Path(..., alias='appPkgId'),
#     request_id: str = Path(..., alias='requestId'),
# ) -> Optional[ProblemDetails]:
#     """
#     Delete a previous usage request
#     """
#     pass

# @router.get(
#     '/app_packages/{appPkgId}/ws',
#     response_model=None,
#     responses={'4XX': {'model': ProblemDetails}, '5XX': {'model': ProblemDetails}},
#     tags=['EaaS Application Repository'],
# )
# def get_app_packages_app_pkg_id_ws(
#     app_pkg_id: str = Path(..., alias='appPkgId')
# ) -> Optional[ProblemDetails]:
#     """
#     Listen to app package update events
#     """
#     pass

#######################################################

# @router.post(
#     '/experiment_descriptors',
#     response_model=None,
#     responses={'201': {'model': ExperimentDescriptorInfo}},
#     tags=['EaaS Experimentation Description Manager'],
# )
# def post_experiment_descriptors(
#     body: CreateExperimentDescriptorInfoRequest,
# ) -> Optional[ExperimentDescriptorInfo]:
#     """
#     Create Experiment Descriptor Info
#     """
#     pass

# @router.get(
#     '/experiment_descriptors/{experimentDescriptorId}',
#     response_model=ExperimentDescriptorInfo,
#     tags=['EaaS Experimentation Description Manager'],
# )
# def get_experiment_descriptors_experiment_descriptor_id(
#     experiment_descriptor_id: str = Path(..., alias='experimentDescriptorId')
# ) -> ExperimentDescriptorInfo:
#     """
#     Read information about an individual Experiment descriptor resource.
#     """
#     pass

# @router.put(
#     '/experiment_descriptors/{experimentDescriptorId}/experimentDescriptor_archive_content',
#     response_model=None,
#     tags=['EaaS Experimentation Description Manager'],
# )
# def put_experiment_descriptors_experiment_descriptor_id_experiment_descriptor_archive_content(
#     experiment_descriptor_id: str = Path(..., alias='experimentDescriptorId')
# ) -> None:
#     """
#     Upload Experiment Descriptor Archive
#     """
#     pass

###########################################################3
# @router.post(
#     '/experiment_instances',
#     response_model=None,
#     responses={'201': {'model': ExperimentInstance}},
#     tags=['EaaS Experimentation Lifecycle Manager'],
# )
# def post_experiment_instances(
#     body: CreateExperimentRequest,
# ) -> Optional[ExperimentInstance]:
#     """
#     Create Experiment Identifier
#     """
#     pass

# @router.post(
#     '/experiment_instances/{experimentInstanceId}/instantiate',
#     response_model=None,
#     tags=['EaaS Experimentation Lifecycle Manager'],
# )
# def post_experiment_instances_experiment_instance_id_instantiate(
#     experiment_instance_id: str = Path(..., alias='experimentInstanceId'),
#     body: InstantiateExperimentRequest = ...,
# ) -> None:
#     """
#     Instantiate Experiment
#     """
#     pass

# @router.post(
#     '/experiment_instances/{experimentInstanceId}/terminate',
#     response_model=None,
#     tags=['EaaS Experimentation Lifecycle Manager'],
# )
# def post_experiment_instances_experiment_instance_id_terminate(
#     experiment_instance_id: str = Path(..., alias='experimentInstanceId'),
#     body: TerminateExperimentRequest = ...,
# ) -> None:
#     """
#     Terminate Experiment
#     """
#     pass
