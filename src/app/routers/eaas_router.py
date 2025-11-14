'''
Experimentation as a Service (EaaS) API Specification
'''
from __future__ import annotations
from typing import Optional  #, Union
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
    AppDescriptor,
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
        response = app_repo_client.get(
            f"/app_packages/{app_package_id}/app_descriptor")
        if config.DEBUG:
            logger.info(f"Response from Application repository: {response.status_code} - {response.text} - {response.json()}")
        response.raise_for_status()
        # FIXME: this needs work
        app_descriptor = AppDescriptor(**response.json())

        # FIXME: Check for artifacts
        # Step 3: Check for application artifacts endpoint
        # Example: if not check_artifacts_available(app_descriptor): raise SomeError()

        # Step 4: Extract and map AppDescriptor and optional [TOSCA??] artifacts to CAMARA AppManifest
        # We need something like: app_manifest = map_to_camara_manifest(app_descriptor, app_artifacts)
        # for now inline, but needs to move
        app_manifest = camara.AppManifest(
            appId='OnBoadrdAppId',
            name=app_descriptor.appProductName,
            appProvider=app_descriptor.appProvider,
            version=app_descriptor.appSoftwareVersion,
            packageType="CONTAINER",
            appRepo=camara.AppRepo(
                type='', imagePath='', userName='',
                credentials=''),  # Get them from AppDescriptor ??
            requiredResources=camara.RequiredResources(),  # FIXME
            componentSpec=[camara.ComponentSpecItem()]  # FIXME
        )
        if config.DEBUG:
            logger.info(f"app manifest for CAMARA: app_manifest={app_manifest}")
        # Step 5: POST to CAMARA /apps
        headers = {}
        if x_correlator:
            headers["x-correlator"] = x_correlator

        response = camara_client.post(
            url="/apps",  # relative to base_url set in client
            json=app_manifest.model_dump(mode="json", exclude_unset=True),
            headers=headers)
        if config.DEBUG:
            logger.info(f"Response from CAMARA API: {response.status_code} - {response.text} - {response.json()}")

        if response.status_code == 201:
            camara_response = camara.SubmittedApp(**response.json())
            if config.DEBUG:
                logger.info(f"camara to pydantic:  {camara_response}")
            app_id = str(camara_response.appId.root
                         ) if camara_response.appId else "unknown-app-id"
            return JSONResponse(status_code=status.HTTP_201_CREATED,
                                content=app_id)

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
        app_onboarding_id = body.appOnboardingId
        additional_params = body.additionalParams or {}

        # Simulate resolving metadata
        app_id = camara.AppId(UUID("123e4567-e89b-12d3-a456-426614174000"))
        app_name = camara.AppInstanceName("MyAppInstance_01")
        edge_cloud_zone_id = additional_params.get("edgeCloudZoneId", "zone-1")
        k8s_ref = additional_params.get("kubernetesClusterRef")

        camara_request = camara.AppinstancesPostRequest(
            name=app_name,
            appId=app_id,
            edgeCloudZoneId=edge_cloud_zone_id,
            kubernetesClusterRef=k8s_ref)

        # Step 2: Call CAMARA /apps/instances
        headers = {}
        if x_correlator:
            headers["x-correlator"] = x_correlator

        response = camara_client.post(
            url="/apps/instances",
            json=camara_request.model_dump(mode="json", exclude_unset=True),
            headers=headers,
        )

        if response.status_code == 201:
            instance_id = response.json().get("instanceId",
                                              "generated-instance-id-456")
            return JSONResponse(status_code=status.HTTP_201_CREATED,
                                content=instance_id)

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
            url=f"/apps/instances/{app_instance_id}", headers=headers)

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


# ---------------------
# /{instanceId}/state/ws
# Somehow confusing (what it the expected behavior?):
# a) ws in the path implies WebSocket protocol, and
#    “Listen to instance state events” strongly reinforces this,
#         suggesting a real-time subscription model.
#     In Swagger or OpenAPI, if this were truly a WebSocket endpoint,
#         it should not use @router.get(...) (HTTP);
#         instead, it would be handled with websocket routes using FastAPI's WebSocket support.
# b) If it’s only polling
#        Then it’s misnamed and misleading — and should just be /state or /status.
# ---------------------
@router.get(
    '/{instanceId}/state/ws',
    response_model=None,
    responses={
        "200": {
            "description": "Application instance state retrieved",
        },
        "4XX": {
            "model": ProblemDetails,
            "description": "Client error"
        },
        "5XX": {
            "model": ProblemDetails,
            "description": "Server error"
        },
    },
    tags=['Southbound Plugin'],
)
def get_instance_id_state_ws(
    instance_id: str = Path(..., alias='instanceId'),
    x_correlator: Optional[str] = Header(None, alias="x-correlator"),
    camara_client: httpx.Client = Depends(get_camara_client),
) -> Optional[ProblemDetails]:
    """
    Fetch the status of a specific application instance by instanceId
    """

    try:
        app_instance_uuid = UUID(instance_id)
    except ValueError:
        return ProblemDetails(
            type="about:blank",
            title="Invalid UUID",
            status=422,
            detail=f"Invalid instanceId format: {instance_id}",
        )

    headers = {}
    if x_correlator:
        headers["x-correlator"] = x_correlator

    try:
        response = camara_client.get(
            url="/apps/instances",
            params={"appInstanceId": str(app_instance_uuid)},
            headers=headers)

        if response.status_code == 200:
            instances = response.json().get("instances", [])
            if not instances:
                return ProblemDetails(
                    type="about:blank",
                    title="Not Found",
                    status=404,
                    detail=f"App instance with ID {instance_id} not found")

            # Get status or default to uknown
            return JSONResponse(
                status_code=200,
                content={"status": instances[0].get("status", "unknown")})

        # 4XX errors from CAMARA
        if 400 <= response.status_code < 500:
            try:
                error = ProblemDetails(
                    type="about:blank",
                    title="Not Found",
                    status=response.status_code,
                    detail=f"CAMARA response: {response.text}")
            except Exception:
                error = ProblemDetails(status=response.status_code,
                                       title="Client error",
                                       detail=response.text)
            return error

        # 5XX errors from CAMARA
        try:
            error = ProblemDetails(type="about:blank",
                                   title="Not Found",
                                   status=response.status_code,
                                   detail=f"CAMARA response: {response.text}")
        except Exception:
            error = ProblemDetails(status=response.status_code,
                                   title="Server error",
                                   detail=response.text)
        return error

    except Exception as ex:
        return ProblemDetails(type="about:blank",
                              title="Internal Server Error",
                              status=500,
                              detail=str(ex))


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
