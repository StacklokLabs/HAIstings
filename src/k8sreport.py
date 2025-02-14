import json
import sh

from typing import List, Set, Tuple


class VulnInfo:
    def __init__(self, id: str, title: str, severity: str):
        self.id = id
        self.title = title
        self.severity = severity
    
    def __str__(self):
        return """
  - ID: {}
    Title: {}
    Severity: {}""".format(self.id, self.title, self.severity)


class ImageWithVulns:
    def __init__(self, srv: str, img: str, digest: str, tag: str, criticalVulns: int, highVulns: int, namespace: str, vulns: List[VulnInfo] = []):
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
            return """image: {}/{}@{}"
namespace: {}
Critical vulns: {}
High vulns: {}
Vulnerabilities: {}
""".format(self.srv, self.img, self.digest, self.namespace, self.criticalVulns, self.highVulns, "\n".join((str(v) for v in self.vulns)))
        return """image: {}/{}:{}
namespace: {}
Critical vulns: {}
High vulns: {}
Vulnerabilities: {}
""".format(self.srv, self.img, self.tag, self.namespace, self.criticalVulns, self.highVulns, "\n".join((str(v) for v in self.vulns)))

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
        if self.criticalVulns * criticalImportance + self.highVulns < other.criticalVulns * criticalImportance + other.highVulns:
            return True
        return False


def gatherVulns() -> Tuple[Set[ImageWithVulns], int, int]:
    vulnsjson = sh.kubectl("get", "vulns", "-A", "-o", "json")
    vulns = json.loads(vulnsjson)

    imgvulns = set()
    totalCritical = 0
    totalHigh = 0

    for vuln in vulns["items"]:
        if ImageWithVulns.hash(
            vuln["report"]["registry"]["server"],
            vuln["report"]["artifact"]["repository"],
            vuln["report"]["artifact"]["digest"],
            vuln["report"]["artifact"].get("tag")) in imgvulns:
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
            vulnList)
        
        totalCritical += img.criticalVulns
        totalHigh += img.highVulns

        imgvulns.add(img)

    return imgvulns, totalCritical, totalHigh


def getVulnList(vulns: list) -> List[VulnInfo]:
    vulnList = []
    for vuln in vulns:
        vulnList.append(VulnInfo(vuln["vulnerabilityID"], vuln["title"], vuln["severity"]))
    return vulnList


def buildreport(imgvulns: set, top: int) -> str:
    out = ""
    out += "## Showing top {} images with most critical vulnerabilities".format(top)

    if len(imgvulns) == 0:
        out += "\nNo vulnerabilities found"
        return out

    if top > len(imgvulns):
        top = len(imgvulns)

    count = 0
    for img in sorted(imgvulns, reverse=True):
        out += img
        if count == top:
            break
        count += 1

    return out


def buildVulnerabilityReport(top: int) -> str:
    imgvulns, _, _ = gatherVulns()

    return buildreport(imgvulns, top)