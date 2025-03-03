from typing import Dict, List, Set

from kubernetes import client, config


class VulnInfo:
    def __init__(self, id: str, title: str, severity: str):
        self.id = id
        self.title = title
        self.severity = severity

    def __str__(self):
        return """
  - ID: {}
    Title: {}
    Severity: {}""".format(
            self.id, self.title, self.severity
        )


class ImageWithVulns:
    def __init__(
        self,
        srv: str,
        img: str,
        digest: str,
        tag: str,
        criticalVulns: int,
        highVulns: int,
        namespace: str,
        vulns: List[VulnInfo] = [],
    ):
        self.srv = srv
        self.img = img
        self.tag = tag
        self.digest = digest
        self.criticalVulns = criticalVulns
        self.highVulns = highVulns
        self.namespace = namespace
        self.vulns = vulns

    def __str__(self):
        if self.tag is None:
            return """- image: {}/{}@{}"
  namespace: {}
  Critical vulns: {}
  High vulns: {}
  Vulnerability IDs: {}
""".format(
                self.srv,
                self.img,
                self.digest,
                self.namespace,
                self.criticalVulns,
                self.highVulns,
                ", ".join((v.id for v in self.vulns)),
            )
        return """- image: {}/{}:{}
  namespace: {}
  Critical vulns: {}
  High vulns: {}
  Vulnerability IDs: {}
""".format(
            self.srv,
            self.img,
            self.tag,
            self.namespace,
            self.criticalVulns,
            self.highVulns,
            ", ".join((v.id for v in self.vulns)),
        )

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if not isinstance(other, ImageWithVulns):
            return
        return self.srv == other.srv and self.img == other.img and self.tag == other.tag and self.digest == other.digest

    # uniqueness is based on image + tag + digest
    def __hash__(self):
        return hash((self.srv, self.img, self.tag, self.digest))

    @classmethod
    def hash(cls, srv: str, img: str, digest: str, tag: str):
        return hash((srv, img, tag, digest))

    # Sort by critical vulns, then by high vulns
    # Critical vulns are 10 times more important than high vulns
    def __lt__(self, other):
        criticalImportance = 10
        if (
            self.criticalVulns * criticalImportance + self.highVulns
            < other.criticalVulns * criticalImportance + other.highVulns
        ):
            return True
        return False


class ReportResult:
    def __init__(
        self,
        images_with_vulns: Set[ImageWithVulns],
        vuln_list: Dict[str, VulnInfo],
        total_critical: int,
        total_high: int,
    ):
        self.images_with_vulns = images_with_vulns
        self.vuln_list = vuln_list
        self.total_critical = total_critical
        self.total_high = total_high


def gatherVulns() -> ReportResult:
    # Load the kube config
    try:
        config.load_kube_config()
    except config.config_exception.ConfigException:
        # If running inside a pod, use the service account credentials
        config.load_incluster_config()

    # Create a custom objects API instance
    api = client.CustomObjectsApi()

    # Get all vulns across all namespaces
    vulns = api.list_cluster_custom_object(
        group="aquasecurity.github.io",
        version="v1alpha1",
        plural="vulnerabilityreports",
    )

    imgvulns = set()
    totalCritical = 0
    totalHigh = 0

    unique_vulns = dict()

    for vuln in vulns["items"]:
        if (
            ImageWithVulns.hash(
                vuln["report"]["registry"]["server"],
                vuln["report"]["artifact"]["repository"],
                vuln["report"]["artifact"]["digest"],
                vuln["report"]["artifact"].get("tag"),
            )
            in imgvulns
        ):
            continue
        vulnList = getVulnList(vuln["report"]["vulnerabilities"])
        img = ImageWithVulns(
            vuln["report"]["registry"]["server"],
            vuln["report"]["artifact"]["repository"],
            vuln["report"]["artifact"]["digest"],
            vuln["report"]["artifact"].get("tag"),
            vuln["report"]["summary"]["criticalCount"],
            vuln["report"]["summary"]["highCount"],
            vuln["metadata"]["namespace"],
            vulnList,
        )

        for vuln in img.vulns:
            if vuln.id not in unique_vulns:
                unique_vulns[vuln.id] = vuln

        totalCritical += img.criticalVulns
        totalHigh += img.highVulns

        imgvulns.add(img)

    return ReportResult(imgvulns, unique_vulns, totalCritical, totalHigh)


def getVulnList(vulns: list) -> List[VulnInfo]:
    vulnList = []
    for vuln in vulns:
        vulnList.append(VulnInfo(vuln["vulnerabilityID"], vuln["title"], vuln["severity"]))
    return vulnList


def buildreport(res: ReportResult, top: int) -> str:
    out = "# Vulnerability report\n\n"

    out += "## Showing top {} images with most critical vulnerabilities".format(top)

    imgvulns = res.images_with_vulns

    if len(imgvulns) == 0:
        out += "\nNo vulnerabilities found"
        return out

    if top > len(imgvulns):
        top = len(imgvulns)

    count = 0
    for img in sorted(imgvulns, reverse=True):
        out += str(img)
        if count == top:
            break
        count += 1

    out += "\n\n## Vulnerability list\n\n"
    out += "\n".join(str(vuln) for _, vuln in res.vuln_list.items())

    out += "\n\n## Summary\n\n"
    out += "Total critical vulnerabilities: {}\n".format(res.total_critical)
    out += "Total high vulnerabilities: {}\n".format(res.total_high)

    return out


def buildVulnerabilityReport(top: int) -> str:
    res = gatherVulns()

    return buildreport(res, top)
