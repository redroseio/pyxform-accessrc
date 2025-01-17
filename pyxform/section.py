# -*- coding: utf-8 -*-
"""
Section survey element module.
"""
from pyxform.errors import PyXFormError
from pyxform.external_instance import ExternalInstance
from pyxform.survey_element import SurveyElement
from pyxform.utils import node


class Section(SurveyElement):
    def validate(self):
        super(Section, self).validate()
        for element in self.children:
            element.validate()
        self._validate_uniqueness_of_element_names()

    # there's a stronger test of this when creating the xpath
    # dictionary for a survey.
    def _validate_uniqueness_of_element_names(self):
        element_slugs = set()
        for element in self.children:
            elem_lower = element.name.lower()
            if elem_lower in element_slugs:
                raise PyXFormError(
                    "There are more than one survey elements named '%s' "
                    "(case-insensitive) in the section named '%s'."
                    % (elem_lower, self.name)
                )
            element_slugs.add(elem_lower)

    def xml_instance(self, **kwargs):
        """
        Creates an xml representation of the section
        """
        append_template = kwargs.pop("append_template", False)

        attributes = {}
        attributes.update(kwargs)
        attributes.update(self.get("instance", {}))
        survey = self.get_root()
        # Resolve field references in attributes
        for key, value in attributes.items():
            attributes[key] = survey.insert_xpaths(value, self)
        result = node(self.name, **attributes)

        for child in self.children:
            repeating_template = None
            if child.get("flat"):
                for grandchild in child.xml_instance_array():
                    result.appendChild(grandchild)
            elif isinstance(child, ExternalInstance):
                continue
            else:
                if isinstance(child, RepeatingSection) and not append_template:
                    append_template = not append_template
                    repeating_template = child.generate_repeating_template()
                result.appendChild(child.xml_instance(append_template=append_template))
            if append_template and repeating_template:
                append_template = not append_template
                result.insertBefore(repeating_template, result._get_lastChild())
        return result

    def generate_repeating_template(self, **kwargs):
        attributes = {"jr:template": ""}
        result = node(self.name, **attributes)
        for child in self.children:
            if isinstance(child, RepeatingSection):
                result.appendChild(child.template_instance())
            else:
                result.appendChild(child.xml_instance())
        return result

    def xml_instance_array(self):
        """
        This method is used for generating flat instances.
        """
        for child in self.children:
            if child.get("flat"):
                for grandchild in child.xml_instance_array():
                    yield grandchild
            else:
                yield child.xml_instance()

    def xml_control(self):
        """
        Ideally, we'll have groups up and rolling soon, but for now
        let's just yield controls from all the children of this section
        """
        for e in self.children:
            control = e.xml_control()
            if control is not None:
                yield control


class RepeatingSection(Section):
    def xml_control(self):
        """
        <group>
        <label>Fav Color</label>
        <repeat nodeset="fav-color">
          <select1 ref=".">
            <label ref="jr:itext('fav')" />
            <item><label ref="jr:itext('red')" /><value>red</value></item>
            <item><label ref="jr:itext('green')" /><value>green</value></item>
            <item><label ref="jr:itext('blue')" /><value>blue</value></item>
          </select1>
        </repeat>
        </group>
        """
        control_dict = self.control.copy()
        survey = self.get_root()
        # Resolve field references in attributes
        for key, value in control_dict.items():
            control_dict[key] = survey.insert_xpaths(value, self)
        repeat_node = node("repeat", nodeset=self.get_xpath(), **control_dict)

        for n in Section.xml_control(self):
            repeat_node.appendChild(n)

        setvalue_nodes = self._get_setvalue_nodes_for_dynamic_defaults()

        for setvalue_node in setvalue_nodes:
            repeat_node.appendChild(setvalue_node)

        label = self.xml_label()
        if label:
            return node("group", self.xml_label(), repeat_node, ref=self.get_xpath())
        return node("group", repeat_node, ref=self.get_xpath(), **self.control)

    # Get setvalue nodes for all descendants of this repeat that have dynamic defaults and aren't nested in other repeats.
    def _get_setvalue_nodes_for_dynamic_defaults(self):
        setvalue_nodes = []
        self._dynamic_defaults_helper(self, setvalue_nodes)
        return setvalue_nodes

    def _dynamic_defaults_helper(self, current, nodes):
        for e in current.children:
            if e.type != "repeat":  # let nested repeats handle their own defaults
                dynamic_default = e.get_setvalue_node_for_dynamic_default(in_repeat=True)
                if dynamic_default:
                    nodes.append(dynamic_default)
                self._dynamic_defaults_helper(e, nodes)

    # I'm anal about matching function signatures when overriding a function,
    # but there's no reason for kwargs to be an argument
    def template_instance(self, **kwargs):
        return super(RepeatingSection, self).generate_repeating_template(**kwargs)


class GroupedSection(Section):
    # I think this might be a better place for the table-list stuff, however it
    # doesn't allow for as good of validation as putting it in xls2json
    # def __init__(self, **kwargs):
    #        control = kwargs.get(u"control")
    #        if control:
    #            appearance = control.get(u"appearance")
    #            if appearance is u"table-list":
    #                print "HI"
    #                control[u"appearance"] = "field-list"
    #                kwargs["children"].insert(0, kwargs["children"][0])
    #        super(GroupedSection, self).__init__(kwargs)

    def xml_control(self):
        control_dict = self.control

        if control_dict.get("bodyless"):
            return None

        children = []
        attributes = {}
        attributes.update(self.control)

        survey = self.get_root()

        # Resolve field references in attributes
        for key, value in attributes.items():
            attributes[key] = survey.insert_xpaths(value, self)

        if not self.get("flat"):
            attributes["ref"] = self.get_xpath()

        if "label" in self and len(self["label"]) > 0:
            children.append(self.xml_label())
        for n in Section.xml_control(self):
            children.append(n)

        if "appearance" in control_dict:
            attributes["appearance"] = control_dict["appearance"]

        if "intent" in control_dict:
            survey = self.get_root()
            attributes["intent"] = survey.insert_xpaths(control_dict["intent"], self)

        return node("group", *children, **attributes)

    def to_json_dict(self):
        # This is quite hacky, might want to think about a smart way
        # to approach this problem.
        result = super(GroupedSection, self).to_json_dict()
        result["type"] = "group"
        return result
