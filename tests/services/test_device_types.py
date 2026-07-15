from argus.services.device_types import get_profile
from argus.services.device_types.base import DeviceTypeProfile, DevfuncRule


def test_get_profile_returns_none_for_unregistered_devgroup():
    assert get_profile("cam") is None
    assert get_profile(None) is None


def test_magnet_devfunc_classification():
    profile = get_profile("mag")
    assert profile.derive_devfunc("QUATB002", "BTF:MAG:OCEME642") == "QUA"
    assert profile.derive_devfunc("CHHTB001", "BTF:MAG") == "COR"
    assert profile.derive_devfunc("DHRTB101", "BTF:MAG") == "DIP"
    assert profile.derive_devfunc("SOLTB001", "BTF:MAG") == "SOL"
    assert profile.derive_devfunc("UNKNOWN01", "BTF:MAG") is None


def test_magnet_key_pvs_built_from_iocprefix_and_name():
    profile = get_profile("mag")
    pvs = profile.key_pvs("BTF:MAG:OCEME642", "QUATB002")
    assert pvs == {
        "current_setpoint": "BTF:MAG:OCEME642:QUATB002:CURRENT_SP",
        "current_readback": "BTF:MAG:OCEME642:QUATB002:CURRENT_RB",
        "state_setpoint": "BTF:MAG:OCEME642:QUATB002:STATE_SP",
        "state_readback": "BTF:MAG:OCEME642:QUATB002:STATE_RB",
    }


def test_vacuum_devfunc_and_key_pvs():
    profile = get_profile("vac")
    assert profile.derive_devfunc("SIP001", "BTF:VAC") == "ion"
    assert profile.derive_devfunc("GAUGE01", "BTF:VAC") is None
    assert profile.key_pvs("BTF:VAC", "GAUGE01") == {"pressure_readback": "BTF:VAC:GAUGE01:PRES_RB"}


def test_motor_mir_rule_checks_iocprefix_but_others_do_not():
    profile = get_profile("mot")
    # MIR rule matches via iocprefix even when the device name doesn't contain it.
    assert profile.derive_devfunc("SOMEDEVICE", "BTF:MIR:STAGE") == "MIR"
    # SLT rule must NOT match via iocprefix -- only the device name.
    assert profile.derive_devfunc("SOMEDEVICE", "BTF:SLT:STAGE") == "MOT"


def test_motor_generic_fallback():
    profile = get_profile("mot")
    assert profile.derive_devfunc("RANDOM01", "BTF:MOT") == "MOT"


def test_motor_has_no_key_pvs_yet():
    profile = get_profile("mot")
    assert profile.key_pvs("BTF:MOT", "RANDOM01") == {}


def test_cooling_key_pvs():
    profile = get_profile("cool")
    assert profile.devfunc_rules == ()
    pvs = profile.key_pvs("BTF:COOL", "CHILLER01")
    assert pvs == {
        "temp_setpoint": "BTF:COOL:CHILLER01:TEMP_SP",
        "temp_readback": "BTF:COOL:CHILLER01:TEMP_RB",
        "state_setpoint": "BTF:COOL:CHILLER01:STATE_SP",
        "state_readback": "BTF:COOL:CHILLER01:STATE_RB",
    }


def test_key_pvs_empty_without_iocprefix():
    profile = get_profile("mag")
    assert profile.key_pvs("", "QUATB002") == {}


def test_devfunc_rules_checked_in_order():
    # A rule appearing earlier in devfunc_rules wins over a later one.
    profile = DeviceTypeProfile(
        devgroup="test",
        devfunc_rules=(
            DevfuncRule(("A",), "FIRST"),
            DevfuncRule(("AB",), "SECOND"),
        ),
    )
    assert profile.derive_devfunc("AB_DEVICE", "") == "FIRST"
