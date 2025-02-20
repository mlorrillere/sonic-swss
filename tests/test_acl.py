import pytest

L3_TABLE_TYPE = "L3"
L3_TABLE_NAME = "L3_TEST"
L3_BIND_PORTS = ["Ethernet0", "Ethernet4", "Ethernet8", "Ethernet12"]
L3_RULE_NAME = "L3_TEST_RULE"

L3V6_TABLE_TYPE = "L3V6"
L3V6_TABLE_NAME = "L3_V6_TEST"
L3V6_BIND_PORTS = ["Ethernet0", "Ethernet4", "Ethernet8"]
L3V6_RULE_NAME = "L3V6_TEST_RULE"


class TestAcl:
    @pytest.yield_fixture
    def l3_acl_table(self, dvs_acl):
        try:
            dvs_acl.create_acl_table(L3_TABLE_NAME, L3_TABLE_TYPE, L3_BIND_PORTS)
            yield dvs_acl.get_acl_table_ids(1)[0]
        finally:
            dvs_acl.remove_acl_table(L3_TABLE_NAME)
            dvs_acl.verify_acl_table_count(0)

    @pytest.yield_fixture
    def l3v6_acl_table(self, dvs_acl):
        try:
            dvs_acl.create_acl_table(L3V6_TABLE_NAME,
                                     L3V6_TABLE_TYPE,
                                     L3V6_BIND_PORTS)
            yield dvs_acl.get_acl_table_ids(1)[0]
        finally:
            dvs_acl.remove_acl_table(L3V6_TABLE_NAME)
            dvs_acl.verify_acl_table_count(0)

    @pytest.yield_fixture
    def setup_teardown_neighbor(self, dvs):
        try:
            # NOTE: set_interface_status has a dependency on cdb within dvs,
            # so we still need to setup the db. This should be refactored.
            dvs.setup_db()

            # Bring up an IP interface with a neighbor
            dvs.set_interface_status("Ethernet4", "up")
            dvs.add_ip_address("Ethernet4", "10.0.0.1/24")
            dvs.add_neighbor("Ethernet4", "10.0.0.2", "00:01:02:03:04:05")

            yield dvs.get_asic_db().wait_for_n_keys("ASIC_STATE:SAI_OBJECT_TYPE_NEXT_HOP", 1)[0]
        finally:
            # Clean up the IP interface and neighbor
            dvs.remove_neighbor("Ethernet4", "10.0.0.2")
            dvs.remove_ip_address("Ethernet4", "10.0.0.1/24")
            dvs.set_interface_status("Ethernet4", "down")

    def test_AclTableCreationDeletion(self, dvs_acl):
        try:
            dvs_acl.create_acl_table(L3_TABLE_NAME, L3_TABLE_TYPE, L3_BIND_PORTS)

            acl_table_id = dvs_acl.get_acl_table_ids(1)[0]
            acl_table_group_ids = dvs_acl.get_acl_table_group_ids(len(L3_BIND_PORTS))

            dvs_acl.verify_acl_table_group_members(acl_table_id, acl_table_group_ids, 1)
            dvs_acl.verify_acl_table_port_binding(acl_table_id, L3_BIND_PORTS, 1)
        finally:
            dvs_acl.remove_acl_table(L3_TABLE_NAME)
            dvs_acl.verify_acl_table_count(0)

    def test_AclRuleL4SrcPort(self, dvs_acl, l3_acl_table):
        config_qualifiers = {"L4_SRC_PORT": "65000"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_L4_SRC_PORT": dvs_acl.get_simple_qualifier_comparator("65000&mask:0xffff")
        }

        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_AclRuleIpProtocol(self, dvs_acl, l3_acl_table):
        config_qualifiers = {"IP_PROTOCOL": "6"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_IP_PROTOCOL": dvs_acl.get_simple_qualifier_comparator("6&mask:0xff")
        }

        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_AclRuleTCPProtocolAppendedForTCPFlags(self, dvs_acl, l3_acl_table):
        """
        Verify TCP Protocol number (6) will be appended for ACL rules matching TCP_FLAGS
        """
        config_qualifiers = {"TCP_FLAGS": "0x07/0x3f"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_TCP_FLAGS":
                dvs_acl.get_simple_qualifier_comparator("7&mask:0x3f"),
            "SAI_ACL_ENTRY_ATTR_FIELD_IP_PROTOCOL":
                dvs_acl.get_simple_qualifier_comparator("6&mask:0xff")
        }
        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_AclRuleNextHeader(self, dvs_acl, l3_acl_table):
        config_qualifiers = {"NEXT_HEADER": "6"}

        # Shouldn't allow NEXT_HEADER on vanilla L3 tables.
        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
        dvs_acl.verify_no_acl_rules()

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleNextHeaderAppendedForTCPFlags(self, dvs_acl, l3v6_acl_table):
        """
        Verify next heder (6) will be appended for IPv6 ACL rules matching TCP_FLAGS
        """
        config_qualifiers = {"TCP_FLAGS": "0x07/0x3f"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_TCP_FLAGS":
                dvs_acl.get_simple_qualifier_comparator("7&mask:0x3f"),
            "SAI_ACL_ENTRY_ATTR_FIELD_IPV6_NEXT_HEADER":
                dvs_acl.get_simple_qualifier_comparator("6&mask:0xff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_AclRuleInOutPorts(self, dvs_acl, l3_acl_table):
        config_qualifiers = {
            "IN_PORTS": "Ethernet0,Ethernet4",
            "OUT_PORTS": "Ethernet8,Ethernet12"
        }

        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_IN_PORTS": dvs_acl.get_port_list_comparator(["Ethernet0", "Ethernet4"]),
            "SAI_ACL_ENTRY_ATTR_FIELD_OUT_PORTS": dvs_acl.get_port_list_comparator(["Ethernet8", "Ethernet12"])
        }

        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_AclRuleInPortsNonExistingInterface(self, dvs_acl, l3_acl_table):
        config_qualifiers = {
            "IN_PORTS": "FOO_BAR_BAZ"
        }

        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)

        dvs_acl.verify_no_acl_rules()
        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)

    def test_AclRuleOutPortsNonExistingInterface(self, dvs_acl, l3_acl_table):
        config_qualifiers = {
            "OUT_PORTS": "FOO_BAR_BAZ"
        }

        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)

        dvs_acl.verify_no_acl_rules()
        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)

    def test_AclRuleVlanId(self, dvs_acl, l3_acl_table):
        config_qualifiers = {"VLAN_ID": "100"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_OUTER_VLAN_ID": dvs_acl.get_simple_qualifier_comparator("100&mask:0xfff")
        }

        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclTableCreationDeletion(self, dvs_acl):
        try:
            dvs_acl.create_acl_table(L3V6_TABLE_NAME,
                                     L3V6_TABLE_TYPE,
                                     L3V6_BIND_PORTS)

            acl_table_id = dvs_acl.get_acl_table_ids(1)[0]
            acl_table_group_ids = dvs_acl.get_acl_table_group_ids(len(L3V6_BIND_PORTS))
            dvs_acl.verify_acl_table_group_members(acl_table_id, acl_table_group_ids, 1)
            dvs_acl.verify_acl_table_port_binding(acl_table_id, L3V6_BIND_PORTS, 1)
        finally:
            dvs_acl.remove_acl_table(L3V6_TABLE_NAME)
            dvs_acl.verify_acl_table_count(0)

    def test_V6AclRuleIPv6Any(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"IP_TYPE": "IPv6ANY"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_ACL_IP_TYPE": dvs_acl.get_simple_qualifier_comparator("SAI_ACL_IP_TYPE_IPV6ANY&mask:0xffffffffffffffff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleIPv6AnyDrop(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"IP_TYPE": "IPv6ANY"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_ACL_IP_TYPE": dvs_acl.get_simple_qualifier_comparator("SAI_ACL_IP_TYPE_IPV6ANY&mask:0xffffffffffffffff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME,
                                L3V6_RULE_NAME,
                                config_qualifiers,
                                action="DROP")
        dvs_acl.verify_acl_rule(expected_sai_qualifiers, action="DROP")

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    # This test validates that backwards compatibility works as expected, it should
    # be converted to a negative test after the 202012 release.
    def test_V6AclRuleIpProtocol(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"IP_PROTOCOL": "6"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_IPV6_NEXT_HEADER": dvs_acl.get_simple_qualifier_comparator("6&mask:0xff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleNextHeader(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"NEXT_HEADER": "6"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_IPV6_NEXT_HEADER": dvs_acl.get_simple_qualifier_comparator("6&mask:0xff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleSrcIPv6(self, dvs_acl, l3v6_acl_table):

        config_qualifiers = {"SRC_IPV6": "2777::0/64"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_SRC_IPV6": dvs_acl.get_simple_qualifier_comparator("2777::&mask:ffff:ffff:ffff:ffff::")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleDstIPv6(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"DST_IPV6": "2002::2/128"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_DST_IPV6": dvs_acl.get_simple_qualifier_comparator("2002::2&mask:ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleL4SrcPort(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"L4_SRC_PORT": "65000"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_L4_SRC_PORT": dvs_acl.get_simple_qualifier_comparator("65000&mask:0xffff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleL4DstPort(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"L4_DST_PORT": "65001"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_L4_DST_PORT": dvs_acl.get_simple_qualifier_comparator("65001&mask:0xffff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleL4SrcPortRange(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"L4_SRC_PORT_RANGE": "1-100"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_ACL_RANGE_TYPE": dvs_acl.get_acl_range_comparator("SAI_ACL_RANGE_TYPE_L4_SRC_PORT_RANGE", "1,100")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleL4DstPortRange(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"L4_DST_PORT_RANGE": "101-200"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_ACL_RANGE_TYPE": dvs_acl.get_acl_range_comparator("SAI_ACL_RANGE_TYPE_L4_DST_PORT_RANGE", "101,200")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_V6AclRuleVlanId(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {"VLAN_ID": "100"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_OUTER_VLAN_ID": dvs_acl.get_simple_qualifier_comparator("100&mask:0xfff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_InsertAclRuleBetweenPriorities(self, dvs_acl, l3_acl_table):
        rule_priorities = ["10", "20", "30", "40"]

        config_qualifiers = {
            "10": {"SRC_IP": "10.0.0.0/32"},
            "20": {"DST_IP": "104.44.94.0/23"},
            "30": {"DST_IP": "192.168.0.16/32"},
            "40": {"DST_IP": "100.64.0.0/10"},
        }

        config_actions = {
            "10": "DROP",
            "20": "DROP",
            "30": "DROP",
            "40": "FORWARD",
        }

        expected_sai_qualifiers = {
            "10": {"SAI_ACL_ENTRY_ATTR_FIELD_SRC_IP": dvs_acl.get_simple_qualifier_comparator("10.0.0.0&mask:255.255.255.255")},
            "20": {"SAI_ACL_ENTRY_ATTR_FIELD_DST_IP": dvs_acl.get_simple_qualifier_comparator("104.44.94.0&mask:255.255.254.0")},
            "30": {"SAI_ACL_ENTRY_ATTR_FIELD_DST_IP": dvs_acl.get_simple_qualifier_comparator("192.168.0.16&mask:255.255.255.255")},
            "40": {"SAI_ACL_ENTRY_ATTR_FIELD_DST_IP": dvs_acl.get_simple_qualifier_comparator("100.64.0.0&mask:255.192.0.0")},
        }

        for rule in rule_priorities:
            dvs_acl.create_acl_rule(L3_TABLE_NAME,
                                    f"PRIORITY_TEST_RULE_{rule}",
                                    config_qualifiers[rule], action=config_actions[rule],
                                    priority=rule)

        dvs_acl.verify_acl_rule_set(rule_priorities, config_actions, expected_sai_qualifiers)

        odd_priority = "21"
        odd_rule = {"ETHER_TYPE": "4660"}
        odd_sai_qualifier = {"SAI_ACL_ENTRY_ATTR_FIELD_ETHER_TYPE": dvs_acl.get_simple_qualifier_comparator("4660&mask:0xffff")}

        rule_priorities.append(odd_priority)
        config_actions[odd_priority] = "DROP"
        expected_sai_qualifiers[odd_priority] = odd_sai_qualifier

        dvs_acl.create_acl_rule(L3_TABLE_NAME,
                                f"PRIORITY_TEST_RULE_{odd_priority}",
                                odd_rule,
                                action="DROP",
                                priority=odd_priority)
        dvs_acl.verify_acl_rule_set(rule_priorities, config_actions, expected_sai_qualifiers)

        for rule in rule_priorities:
            dvs_acl.remove_acl_rule(L3_TABLE_NAME, f"PRIORITY_TEST_RULE_{rule}")
        dvs_acl.verify_no_acl_rules()

    def test_RulesWithDiffMaskLengths(self, dvs_acl, l3_acl_table):
        rule_priorities = ["10", "20", "30", "40", "50", "60"]

        config_qualifiers = {
            "10": {"SRC_IP": "23.103.0.0/18"},
            "20": {"SRC_IP": "104.44.94.0/23"},
            "30": {"DST_IP": "172.16.0.0/12"},
            "40": {"DST_IP": "100.64.0.0/10"},
            "50": {"DST_IP": "104.146.32.0/19"},
            "60": {"SRC_IP": "21.0.0.0/8"},
        }

        config_actions = {
            "10": "FORWARD",
            "20": "FORWARD",
            "30": "FORWARD",
            "40": "FORWARD",
            "50": "FORWARD",
            "60": "FORWARD",
        }

        expected_sai_qualifiers = {
            "10": {"SAI_ACL_ENTRY_ATTR_FIELD_SRC_IP": dvs_acl.get_simple_qualifier_comparator("23.103.0.0&mask:255.255.192.0")},
            "20": {"SAI_ACL_ENTRY_ATTR_FIELD_SRC_IP": dvs_acl.get_simple_qualifier_comparator("104.44.94.0&mask:255.255.254.0")},
            "30": {"SAI_ACL_ENTRY_ATTR_FIELD_DST_IP": dvs_acl.get_simple_qualifier_comparator("172.16.0.0&mask:255.240.0.0")},
            "40": {"SAI_ACL_ENTRY_ATTR_FIELD_DST_IP": dvs_acl.get_simple_qualifier_comparator("100.64.0.0&mask:255.192.0.0")},
            "50": {"SAI_ACL_ENTRY_ATTR_FIELD_DST_IP": dvs_acl.get_simple_qualifier_comparator("104.146.32.0&mask:255.255.224.0")},
            "60": {"SAI_ACL_ENTRY_ATTR_FIELD_SRC_IP": dvs_acl.get_simple_qualifier_comparator("21.0.0.0&mask:255.0.0.0")},
        }

        for rule in rule_priorities:
            dvs_acl.create_acl_rule(L3_TABLE_NAME,
                                    f"MASK_TEST_RULE_{rule}",
                                    config_qualifiers[rule],
                                    action=config_actions[rule],
                                    priority=rule)
        dvs_acl.verify_acl_rule_set(rule_priorities, config_actions, expected_sai_qualifiers)

        for rule in rule_priorities:
            dvs_acl.remove_acl_rule(L3_TABLE_NAME, f"MASK_TEST_RULE_{rule}")
        dvs_acl.verify_no_acl_rules()

    def test_AclRuleIcmp(self, dvs_acl, l3_acl_table):
        config_qualifiers = {
            "ICMP_TYPE": "8",
            "ICMP_CODE": "9"
        }

        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_ICMP_TYPE": dvs_acl.get_simple_qualifier_comparator("8&mask:0xff"),
            "SAI_ACL_ENTRY_ATTR_FIELD_ICMP_CODE": dvs_acl.get_simple_qualifier_comparator("9&mask:0xff")
        }

        dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

        dvs_acl.remove_acl_table(L3_TABLE_NAME)
        dvs_acl.verify_acl_table_count(0)

    def test_AclRuleIcmpV6(self, dvs_acl, l3v6_acl_table):
        config_qualifiers = {
            "ICMPV6_TYPE": "8",
            "ICMPV6_CODE": "9"
        }

        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_ICMPV6_TYPE": dvs_acl.get_simple_qualifier_comparator("8&mask:0xff"),
            "SAI_ACL_ENTRY_ATTR_FIELD_ICMPV6_CODE": dvs_acl.get_simple_qualifier_comparator("9&mask:0xff")
        }

        dvs_acl.create_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME, config_qualifiers)
        dvs_acl.verify_acl_rule(expected_sai_qualifiers)

        dvs_acl.remove_acl_rule(L3V6_TABLE_NAME, L3V6_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

    def test_AclRuleRedirect(self, dvs, dvs_acl, l3_acl_table, setup_teardown_neighbor):
        config_qualifiers = {"L4_SRC_PORT": "65000"}
        expected_sai_qualifiers = {
            "SAI_ACL_ENTRY_ATTR_FIELD_L4_SRC_PORT": dvs_acl.get_simple_qualifier_comparator("65000&mask:0xffff")
        }

        dvs_acl.create_redirect_acl_rule(L3_TABLE_NAME,
                                         L3_RULE_NAME,
                                         config_qualifiers,
                                         intf="Ethernet4",
                                         ip="10.0.0.2",
                                         priority="20")

        next_hop_id = setup_teardown_neighbor
        dvs_acl.verify_redirect_acl_rule(expected_sai_qualifiers, next_hop_id, priority="20")

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()

        dvs_acl.create_redirect_acl_rule(L3_TABLE_NAME,
                                         L3_RULE_NAME,
                                         config_qualifiers,
                                         intf="Ethernet4",
                                         priority="20")

        intf_id = dvs.asic_db.port_name_map["Ethernet4"]
        dvs_acl.verify_redirect_acl_rule(expected_sai_qualifiers, intf_id, priority="20")

        dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
        dvs_acl.verify_no_acl_rules()


class TestAclCrmUtilization:
    @pytest.fixture(scope="class", autouse=True)
    def configure_crm_polling_interval_for_test(self, dvs):
        dvs.runcmd("crm config polling interval 1")

        yield

        dvs.runcmd("crm config polling interval 300")

    def test_ValidateAclTableBindingCrmUtilization(self, dvs, dvs_acl):
        counter_db = dvs.get_counters_db()

        crm_port_stats = counter_db.get_entry("CRM", "ACL_STATS:INGRESS:PORT")
        initial_acl_table_port_bindings_used = int(crm_port_stats.get("crm_stats_acl_table_used", 0))

        crm_lag_stats = counter_db.get_entry("CRM", "ACL_STATS:INGRESS:LAG")
        initial_acl_table_lag_bindings_used = int(crm_lag_stats.get("crm_stats_acl_table_used", 0))

        dvs_acl.create_acl_table(L3_TABLE_NAME, L3_TABLE_TYPE, L3_BIND_PORTS)
        dvs_acl.verify_acl_table_count(1)

        counter_db.wait_for_field_match(
            "CRM",
            "ACL_STATS:INGRESS:PORT",
            {"crm_stats_acl_table_used": str(initial_acl_table_port_bindings_used + 1)}
        )

        counter_db.wait_for_field_match(
            "CRM",
            "ACL_STATS:INGRESS:LAG",
            {"crm_stats_acl_table_used": str(initial_acl_table_lag_bindings_used + 1)}
        )

        dvs_acl.remove_acl_table(L3_TABLE_NAME)
        dvs_acl.verify_acl_table_count(0)

        counter_db.wait_for_field_match(
            "CRM",
            "ACL_STATS:INGRESS:PORT",
            {"crm_stats_acl_table_used": str(initial_acl_table_port_bindings_used)}
        )

        counter_db.wait_for_field_match(
            "CRM",
            "ACL_STATS:INGRESS:LAG",
            {"crm_stats_acl_table_used": str(initial_acl_table_lag_bindings_used)}
        )


# TODO: Need to improve the clean-up/post-checks for these tests as currently we can't run anything
# afterwards.
class TestAclRuleValidation:
    """Test class for cases that check if orchagent corectly validates ACL rules input."""

    SWITCH_CAPABILITY_TABLE = "SWITCH_CAPABILITY"

    def get_acl_actions_supported(self, dvs_acl, stage):
        switch_id = dvs_acl.state_db.wait_for_n_keys(self.SWITCH_CAPABILITY_TABLE, 1)[0]
        switch = dvs_acl.state_db.wait_for_entry(self.SWITCH_CAPABILITY_TABLE, switch_id)

        field = "ACL_ACTIONS|{}".format(stage.upper())

        supported_actions = switch.get(field, None)

        if supported_actions:
            supported_actions = supported_actions.split(",")
        else:
            supported_actions = []

        return supported_actions

    def test_AclActionValidation(self, dvs, dvs_acl):
        """
            The test overrides R/O SAI_SWITCH_ATTR_ACL_STAGE_INGRESS/EGRESS switch attributes
            to check the case when orchagent refuses to process rules with action that is not
            supported by the ASIC.
        """

        stage_name_map = {
            "ingress": "SAI_SWITCH_ATTR_ACL_STAGE_INGRESS",
            "egress": "SAI_SWITCH_ATTR_ACL_STAGE_EGRESS",
        }

        for stage in stage_name_map:
            action_values = self.get_acl_actions_supported(dvs_acl, stage)

            # virtual switch supports all actions
            assert action_values
            assert "PACKET_ACTION" in action_values

            sai_acl_stage = stage_name_map[stage]

            # mock switch attribute in VS so only REDIRECT action is supported on this stage
            dvs.setReadOnlyAttr("SAI_OBJECT_TYPE_SWITCH",
                                sai_acl_stage,
                                # FIXME: here should use sai_serialize_value() for acl_capability_t
                                #        but it is not available in VS testing infrastructure
                                "false:1:SAI_ACL_ACTION_TYPE_REDIRECT")

            # restart SWSS so orchagent will query updated switch attributes
            dvs.stop_swss()
            dvs.start_swss()
            # reinit ASIC DB validator object
            dvs.init_asic_db_validator()

            action_values = self.get_acl_actions_supported(dvs_acl, stage)
            # Now, PACKET_ACTION is not supported and REDIRECT_ACTION is supported
            assert "PACKET_ACTION" not in action_values
            assert "REDIRECT_ACTION" in action_values

            # try to create a forward rule
            try:
                dvs_acl.create_acl_table(L3_TABLE_NAME,
                                         L3_TABLE_TYPE,
                                         L3_BIND_PORTS,
                                         stage=stage)

                config_qualifiers = {
                    "ICMP_TYPE": "8"
                }

                dvs_acl.create_acl_rule(L3_TABLE_NAME, L3_RULE_NAME, config_qualifiers)
                dvs_acl.verify_no_acl_rules()
            finally:
                dvs_acl.remove_acl_rule(L3_TABLE_NAME, L3_RULE_NAME)
                dvs_acl.remove_acl_table(L3_TABLE_NAME)

                dvs.runcmd("supervisorctl restart syncd")
                dvs.stop_swss()
                dvs.start_swss()


# Add Dummy always-pass test at end as workaroud
# for issue when Flaky fail on final test it invokes module tear-down before retrying
def test_nonflaky_dummy():
    pass
