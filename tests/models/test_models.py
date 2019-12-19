import json
import pathlib
from typing import Any, Dict, List, NamedTuple, Tuple

import ntc_rosetta

import pytest

Data = NamedTuple(
    "Data",
    [
        ("org", str),
        ("model", str),
        ("driver", str),
        ("action", str),
        ("path", pathlib.Path),
    ],
)

filters: Dict[str, Dict[str, List[str]]] = {
    "ntc-vlan": {"include": [], "exclude": []},
    "openconfig-interfaces": {
        "include": [
            "/openconfig-interfaces:interfaces/interface/name",
            "/openconfig-interfaces:interfaces/interface/config",
            "/openconfig-interfaces:interfaces/interface/state",
            "/openconfig-interfaces:interfaces/interface/hold-time",
            "/openconfig-interfaces:interfaces/interface/subinterfaces/subinterface/index",
            "/openconfig-interfaces:interfaces/interface/subinterfaces/subinterface/config",
            "/openconfig-interfaces:interfaces/interface/subinterfaces/subinterface/state",
        ],
        "exclude": [],
    },
    "openconfig-vlan": {
        "include": [
            "/openconfig-interfaces:interfaces",
            "/openconfig-network-instance:network-instances/network-instance/name",
            "/openconfig-network-instance:network-instances/network-instance/config",
            "/openconfig-network-instance:network-instances/network-instance/vlans",
        ],
        "exclude": [],
    },
    "openconfig-system": {
        "include": [
            "/openconfig-system:system/clock/config",
            "/openconfig-system:system/clock",
            "/openconfig-system:system/dns/config",
            "/openconfig-system:system/dns/servers/server/config",
            "/openconfig-system:system/dns/servers/server",
            "/openconfig-system:system/dns/servers",
            "/openconfig-system:system/dns",
            "/openconfig-system:system/ntp/config",
            "/openconfig-system:system/ntp/servers/server/config",
            "/openconfig-system:system/ntp/servers/server",
            "/openconfig-system:system/ntp/servers",
            "/openconfig-system:system/ntp",
            "/openconfig-system:system/ssh-server/config",
            "/openconfig-system:system/ssh-server",
            "/openconfig-system:system/telnet-server/config",
            "/openconfig-system:system/telnet-server",
            "/openconfig-system:system/aaa/authentication/users/user/config",
            "/openconfig-system:system/aaa/authentication/users/user",
            "/openconfig-system:system/aaa/authentication/users",
            "/openconfig-system:system/aaa/authentication",
            "/openconfig-system:system/aaa/server-groups/server-group/servers/server/tacacs/config",
            "/openconfig-system:system/aaa/server-groups/server-group/servers/server/tacacs",
            "/openconfig-system:system/aaa/server-groups/server-group/servers/server",
            "/openconfig-system:system/aaa/server-groups/server-group/servers",
            "/openconfig-system:system/aaa/server-groups/server-group",
            "/openconfig-system:system/aaa/server-groups",
            "/openconfig-system:system/aaa",
            "/openconfig-system:system/config",
            "/openconfig-system:system",
        ],
        "exclude": [],
    },
}


def valid_dir(path: pathlib.Path) -> bool:
    if not path.is_dir() or path.name == "__pycache__":
        return False
    return True


def get_test_cases(test: str) -> Dict[str, Any]:
    base = pathlib.Path(__file__).parent

    test_cases: List[Tuple[str, str, str, pathlib.Path]] = []
    ids: List[str] = []
    for model_path in base.iterdir():
        org = model_path.name
        if not valid_dir(model_path):
            continue
        for data_path in model_path.joinpath(f"data").iterdir():
            if not valid_dir(data_path):
                continue
            model = data_path.name
            for driver_path in sorted(data_path.joinpath(test).iterdir()):
                if not valid_dir(driver_path):
                    continue
                driver = driver_path.name
                for test_case_path in sorted(driver_path.iterdir()):
                    if not valid_dir(test_case_path):
                        continue
                    test_case = test_case_path.name
                    ids.append(f"{model}_{driver}_{test_case}")
                    test_cases.append((org, model, driver, test_case_path))
    return {
        "argnames": "org,model,driver,test_case_path",
        "argvalues": test_cases,
        "ids": ids,
    }


class Test:
    @pytest.mark.parametrize(**get_test_cases("parse"))  # type: ignore
    def test_parser(
        self, org: str, model: str, driver: str, test_case_path: pathlib.Path
    ) -> None:
        with open(test_case_path.joinpath("dev_conf"), "r") as f:
            dev_conf = f.read()
        with open(test_case_path.joinpath("result.json"), "r") as f:
            structured = json.load(f)

        driver_class = ntc_rosetta.get_driver(driver, org)
        device = driver_class()

        parsed_obj = device.parse(
            native={"dev_conf": dev_conf},
            validate=False,
            include=filters[model.replace("_", "-")]["include"],
            exclude=filters[model.replace("_", "-")]["exclude"],
        )
        #  print(json.dumps(parsed_obj.raw_value()))
        assert parsed_obj.raw_value() == structured, json.dumps(parsed_obj.raw_value())

    def _test_translate(
        self, org: str, driver: str, test_case_path: pathlib.Path, mode: str
    ) -> None:
        with open(test_case_path.joinpath("data.json"), "r") as f:
            candidate = json.load(f)
        with open(test_case_path.joinpath(f"res_{mode}"), "r") as f:
            expected = f.read()
        driver_class = ntc_rosetta.get_driver(driver, org)
        device = driver_class()
        config = device.translate(candidate, replace=mode == "replace")
        assert config == expected

    @pytest.mark.parametrize(**get_test_cases("translate"))  # type: ignore
    def test_translate_merge(
        self, org: str, model: str, driver: str, test_case_path: pathlib.Path
    ) -> None:
        self._test_translate(org, driver, test_case_path, "merge")

    @pytest.mark.parametrize(**get_test_cases("translate"))  # type: ignore
    def test_translate_replace(
        self, org: str, model: str, driver: str, test_case_path: pathlib.Path
    ) -> None:
        self._test_translate(org, driver, test_case_path, "replace")


def parse_path(pathname: str) -> Data:
    """Parse a given test path into a useful object

    Args:
        pathname: string, path must conform to
            `tests/models/{org}/data/{model}/{action}/{driver}`

    Returns:
        A namedtuple of strings

    """
    path = pathlib.Path(pathname)
    action = path.parents[2].stem
    driver = path.parents[1].stem
    model = path.parents[3].stem.replace("_", "-")
    org = path.parents[5].stem
    return Data(org, model, driver, action, path.parent)


def merge(org: str, driver: str, test_case_path: pathlib.Path, mode: str) -> None:
    """Run merge test on models with given data.

    Args:
        org: YANG organization
        driver: ntc-rosetta driver
        test_case_path: parsed __file__ attribute of caller
        mode: options of {"replace", "merge"}

    """
    with open(test_case_path.joinpath("data_candidate.json"), "r") as f:
        candidate = json.load(f)
    with open(test_case_path.joinpath("data_running.json"), "r") as f:
        running = json.load(f)
    with open(test_case_path.joinpath(f"res_{mode}"), "r") as f:
        expected = f.read()
    driver_class = ntc_rosetta.get_driver(driver, org)
    device = driver_class()
    res_merge = device.merge(candidate, running, replace=mode == "replace")
    assert res_merge == expected
