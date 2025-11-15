from typing import Any, Dict, List, Optional
from pydantic import ValidationError
from app.models.eaas_models import (
    AppDescriptor,
    SwImageDesc,
    OsContainerDesc,
    VDU,
    AppExtCpd,
    VirtualCpd,
    DeploymentFlavour,
)

def build_app_descriptor_from_repo_payload(payload: Dict[str, Any]) -> AppDescriptor:
    """
    Adapt the JSON from the Application Repository so it matches
    our internal Pydantic models, then build an AppDescriptor.
    """

    # ---------- 1) Base scalar fields ----------
    base_kwargs = {
        "appDescriptorId": payload["appDescriptorId"],
        "appDescriptorExtInvariantId": payload["appDescriptorExtInvariantId"],
        "appProvider": payload["appProvider"],
        "appProductName": payload["appProductName"],
        "appSoftwareVersion": payload["appSoftwareVersion"],
        "appDescriptorVersion": payload["appDescriptorVersion"],
        "appmInfo": payload.get("appmInfo"),
    }

    # ---------- 2) swImageDesc: full objects ----------
    raw_sw_images = payload.get("swImageDesc") or []
    sw_images: List[SwImageDesc] = [SwImageDesc(**img) for img in raw_sw_images]

    # map id -> SwImageDesc
    sw_image_by_id: Dict[str, SwImageDesc] = {
        img.id: img for img in sw_images  # assuming SwImageDesc has field "id"
    }

    # ---------- 3) osContainerDesc: plug in SwImageDesc objects ----------
    raw_os_containers = payload.get("osContainerDesc") or []
    os_containers: List[OsContainerDesc] = []
    os_container_by_id: Dict[str, OsContainerDesc] = {}

    for oc in raw_os_containers:
        # "swImageDesc" is an ID string in the payload
        sw_id = oc.get("swImageDesc")
        oc_data = {k: v for k, v in oc.items() if k != "swImageDesc"}

        if isinstance(sw_id, str) and sw_id in sw_image_by_id:
            oc_data["swImageDesc"] = sw_image_by_id[sw_id]

        os_obj = OsContainerDesc(**oc_data)
        os_containers.append(os_obj)
        os_container_by_id[os_obj.osContainerDescId] = os_obj

    # ---------- 4) VDU: replace osContainerDesc IDs with full objects ----------
    raw_vdus = payload.get("vdu") or []
    vdu_list: List[VDU] = []

    for v in raw_vdus:
        oc_ids = v.get("osContainerDesc") or []
        resolved_oc: List[OsContainerDesc] = []

        if isinstance(oc_ids, list):
            for oc_id in oc_ids:
                if isinstance(oc_id, str) and oc_id in os_container_by_id:
                    resolved_oc.append(os_container_by_id[oc_id])

        v_data = {k: v for k, v in v.items() if k != "osContainerDesc"}
        v_data["osContainerDesc"] = resolved_oc

        vdu_list.append(VDU(**v_data))

    # ---------- 5) appExtCpd ----------
    raw_app_ext_cpd = payload.get("appExtCpd") or []
    app_ext_cpd: Optional[List[AppExtCpd]] = (
        [AppExtCpd(**c) for c in raw_app_ext_cpd] if raw_app_ext_cpd else None
    )

    # ---------- 6) virtualCpd ----------
    raw_virtual_cpd = payload.get("virtualCpd") or []
    virtual_cpd: Optional[List[VirtualCpd]] = (
        [VirtualCpd(**c) for c in raw_virtual_cpd] if raw_virtual_cpd else None
    )

    # ---------- 7) deploymentFlavour ----------
    raw_df_list = payload.get("deploymentFlavour") or []

    # If your DeploymentFlavour model uses "instantiationLevel" but
    # the payload sends "istantiationLevel", fix it here:
    for df in raw_df_list:
        if "istantiationLevel" in df and "instantiationLevel" not in df:
            df["instantiationLevel"] = df.pop("istantiationLevel")

    deployment_flavours: Optional[List[DeploymentFlavour]] = (
        [DeploymentFlavour(**df) for df in raw_df_list] if raw_df_list else None
    )

    # ---------- 8) Finally build AppDescriptor ----------
    return AppDescriptor(
        **base_kwargs,
        swImageDesc=sw_images or None,
        vdu=vdu_list or None,
        deploymentFlavour=deployment_flavours,
        appExtCpd=app_ext_cpd,
        virtualCpd=virtual_cpd,
    )
