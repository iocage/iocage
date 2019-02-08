from unittest.mock import Mock, patch

from iocage_lib.ioc_json import IOCCpuset

# For cpuset props we would like to test the following scenarios
# 1) 0,1,2,3
# 2) 0-3
# 3) all
# 4) off


# Tests for point 1
def test_01_full_range():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=6)
    ):
        assert IOCCpuset.validate_cpuset_prop('0,1,2,3,4,5', False) is False


def test_02_subset_of_complete_range():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=6)
    ):
        assert IOCCpuset.validate_cpuset_prop('1,2,3', False) is False


def test_03_order_is_irrelevant():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=60)
    ):
        assert IOCCpuset.validate_cpuset_prop('2,1,4,11', False) is False


def test_04_duplicates_are_not_allowed():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=60)
    ):
        assert IOCCpuset.validate_cpuset_prop('1,2,1', False) is True


def test_05_order_for_commas_to_be_respected():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=60)
    ):
        assert IOCCpuset.validate_cpuset_prop('1,2,', False) is True
        assert IOCCpuset.validate_cpuset_prop(',1,2', False) is True


def test_06_invalid_cpuset_value_not_allowed():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=60)
    ):
        assert IOCCpuset.validate_cpuset_prop('1,2,99', False) is True


def test_07_cpuset_value_not_retrieved():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=-2)
    ):
        assert IOCCpuset.validate_cpuset_prop('1,2,99', False) is True


def test_08_single_cpuset_value():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=0)
    ):
        assert IOCCpuset.validate_cpuset_prop('0', False) is False


# Tests for point 2
def test_09_valid_range():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=60)
    ):
        assert IOCCpuset.validate_cpuset_prop('0-59', False) is False


def test_10_invalid_range_not_allowed():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=60)
    ):
        assert IOCCpuset.validate_cpuset_prop('0-99', False) is True


def test_11_subset_of_cpus_in_range():
    with patch(
        'iocage_lib.ioc_json.IOCCpuset.retrieve_cpu_sets',
        Mock(return_value=60)
    ):
        assert IOCCpuset.validate_cpuset_prop('12-22', False) is False


# Tests for point 3 and 4
def test_12_off_value():
    assert IOCCpuset.validate_cpuset_prop('off', False) is False


def test_13_all_value():
    assert IOCCpuset.validate_cpuset_prop('all', False) is False


def test_14_invalid_value_not_allowed():
    assert IOCCpuset.validate_cpuset_prop('gibberish', False) is True
