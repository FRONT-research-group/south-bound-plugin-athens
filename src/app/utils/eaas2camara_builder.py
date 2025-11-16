import re
from typing import List, Dict, Any, Optional
from uuid import UUID
from enum import Enum as PyEnum 
from app.models.eaas_models import AppDescriptor, VDU, OsContainerDesc, SwImageDesc
import app.models.camara_models as camara
from app.utils.logger import logger


def _sanitize_app_name(raw: str) -> str:
    """
    CAMARA AppManifest.name: ^[A-Za-z][A-Za-z0-9_]{1,63}$
    """
    if not raw:
        return "App_1"

    # Replace non-alnum with underscores
    s = re.sub(r'[^A-Za-z0-9_]', '_', raw)

    # Ensure starts with a letter
    if not re.match(r'^[A-Za-z]', s):
        s = 'A' + s

    # Enforce length (2..64 total)
    if len(s) < 2:
        s = s + "_1"
    if len(s) > 64:
        s = s[:64]

    # Ensure at least 2 chars and pattern matches
    if not re.match(r'^[A-Za-z][A-Za-z0-9_]{1,63}$', s):
        s = "App_" + s[:60]

    return s


def _sanitize_app_provider(raw: str) -> str:
    """
    CAMARA AppProvider: ^[A-Za-z][A-Za-z0-9_]{7,63}$ (length 8..64)
    """
    if not raw:
        raw = "Provider_00000000"

    s = re.sub(r'[^A-Za-z0-9_]', '_', raw)

    if not re.match(r'^[A-Za-z]', s):
        s = "P_" + s  # ensure starts with letter

    # ensure minimum length 8
    if len(s) < 8:
        s = s + "_provider"
    # max 64
    if len(s) > 64:
        s = s[:64]

    # final fallback
    if not re.match(r'^[A-Za-z][A-Za-z0-9_]{7,63}$', s):
        s = "Provider_" + re.sub(r'[^A-Za-z0-9_]', '_', s)[:55]

    return s


def _sanitize_interface_id(raw: str) -> str:
    """
    NetworkInterface.interfaceId: ^[A-Za-z][A-Za-z0-9_]{3,31}$ (length 4..32)
    """
    if not raw:
        raw = "eth0"

    s = re.sub(r'[^A-Za-z0-9_]', '_', raw)

    if not re.match(r'^[A-Za-z]', s):
        s = "i_" + s

    if len(s) < 4:
        s = s + "_eth"
    if len(s) > 32:
        s = s[:32]

    if not re.match(r'^[A-Za-z][A-Za-z0-9_]{3,31}$', s):
        s = "if_" + s[:30]

    return s


def _sanitize_component_name(raw: str) -> str:
    # Just reuse app name rules, less strict.
    return _sanitize_app_name(raw)



def build_camara_app_manifest(app_descriptor: AppDescriptor) -> camara.AppManifest:
    """
    Transform an EaaS AppDescriptor into a CAMARA AppManifest.
    Assumes a container/Kubernetes-style deployment.
    """

    # ---------- 1) Basic app identity ----------

    # Let CAMARA platform generate appId → keep None
    logger.info("************ Building CAMARA AppManifest from AppDescriptor *********")
    app_id: Optional[camara.AppId] = None
    name = _sanitize_app_name(app_descriptor.appProductName)
    provider_name = _sanitize_app_provider(app_descriptor.appProvider)
    app_provider = camara.AppProvider(provider_name)
    version = app_descriptor.appSoftwareVersion

    # ---------- 2) Image / AppRepo ----------

    image_name = "app"
    image_version = "latest"
    if app_descriptor.swImageDesc:
        img = app_descriptor.swImageDesc[0]  # first image
        # depending on your SwImageDesc model field names:
        image_name = getattr(img, "swImage", None) or getattr(img, "name", "app")
        image_version = getattr(img, "version", "latest")

    # naive default; adjust to your registry
    image_path_str = f"docker.io/library/{image_name}:{image_version}"
    app_repo = camara.AppRepo(
        type=camara.Type.PUBLICREPO,
        imagePath=camara.Uri(image_path_str),
        userName=None,
        credentials=None,
        authType=None,
        checksum=None,
    )

    # ---------- 3) RequiredResources (Kubernetes) ----------
    total_cpu = 0
    total_mem = 0  # MB

    for vdu in app_descriptor.vdu or []:
        for oc in vdu.osContainerDesc or []:
            # CPU
            if oc.requestedCpuResources is not None:
                total_cpu += oc.requestedCpuResources
            elif oc.cpuResourceLimit is not None:
                total_cpu += oc.cpuResourceLimit

            # Memory (assuming MB)
            if oc.memoryResourceLimit is not None:
                total_mem += int(oc.memoryResourceLimit)
            elif oc.requestedMemoryResource is not None:
                total_mem += int(oc.requestedMemoryResource)
    if total_cpu <= 0:
        total_cpu = 1
    if total_mem <= 0:
        total_mem = 1024

    topology = camara.Topology(
        minNumberOfNodes=1,
        minNodeCpu=max(1, total_cpu),
        minNodeMemory=total_mem,
    )
    cpu_pool = camara.CpuPool(
        numCPU=total_cpu,
        memory=total_mem,
        topology=topology,
    )
    app_resources = camara.ApplicationResources(
        cpuPool=cpu_pool,
        gpuPool=None,
    )
    k8s_resources = camara.KubernetesResources(
        infraKind="kubernetes",
        applicationResources=app_resources,
        isStandalone=True,
        version=None,      # or "1.28"
        additionalStorage=None,
        networking=None,
        addons=None,
    )
    required_resources = camara.RequiredResources(root=k8s_resources)

    # ---------- 4) ComponentSpec (network interfaces) ----------
    # Build map VDU_ID -> list of virtualCpd
    vcpd_by_vdu_id: Dict[str, List[Any]] = {}
    for vcpd in app_descriptor.virtualCpd or []:
        for vdu_id in vcpd.vdu or []:
            vcpd_by_vdu_id.setdefault(vdu_id, []).append(vcpd)
    component_spec: List[camara.ComponentSpecItem] = []


    for vdu in app_descriptor.vdu or []:
        netifs: List[camara.NetworkInterface] = []

        for vcpd in vcpd_by_vdu_id.get(vdu.vduId, []):

            for asd in (vcpd.additionalServiceData or []):

                for pd in (asd.portData or []):

                    interface_id = _sanitize_interface_id(
                        pd.name or f"{vdu.vduId}_{vcpd.cpdId}"
                    )

                    # ---- HERE IS THE IMPORTANT CHANGE ----
                    proto = pd.protocol

                    # If it's an Enum (like your Protocol), use .value
                    if isinstance(proto, PyEnum):
                        protocol_str = proto.value
                    else:
                        protocol_str = proto or "TCP"

                    protocol_str = str(protocol_str).upper()

                    try:
                        protocol_enum = camara.Protocol[protocol_str]
                    except KeyError:
                        logger.warning(
                            "Unknown protocol '%s', using ANY", protocol_str
                        )
                        protocol_enum = camara.Protocol.ANY

                    netifs.append(
                        camara.NetworkInterface(
                            interfaceId=interface_id,
                            protocol=protocol_enum,
                            port=pd.port,
                            visibilityType=camara.VisibilityType.VISIBILITY_INTERNAL,
                        )
                    )

        if netifs:
            comp_name = _sanitize_component_name(vdu.name or vdu.vduId)
            component_spec.append(
                camara.ComponentSpecItem(
                    componentName=comp_name,
                    networkInterfaces=netifs,
                )
            )

    # Fallback: ensure at least one componentSpec
    if not component_spec:
        component_spec.append(
            camara.ComponentSpecItem(
                componentName=_sanitize_component_name(app_descriptor.appProductName),
                networkInterfaces=[],
            )
        )

    # ---------- 5) Build and return AppManifest ----------

    app_manifest = camara.AppManifest(
        appId=app_id,
        name=name,
        appProvider=app_provider,
        version=version,
        packageType=camara.PackageType.CONTAINER,
        operatingSystem=None,
        appRepo=app_repo,
        requiredResources=required_resources,
        componentSpec=component_spec,
    )

    return app_manifest
