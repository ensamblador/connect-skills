"""Auto-generated. Do not edit by hand.

Regenerate with:
    uv run python .kiro/skills/connect-view-author/scripts/refresh_connect_view_component_types.py

Source:
    https://d3irlmavjxd3d8.cloudfront.net/  (Amazon Connect View Dictionary)
"""

VALID_VIEW_COMPONENT_TYPES: frozenset[str] = frozenset({
    "Alert",
    "Application",
    "AttributeBar",
    "AttributeSection",
    "Button",
    "ButtonGroup",
    "Card",
    "Cards",
    "CheckboxGroup",
    "Confirmation",
    "Container",
    "DatePicker",
    "Detail",
    "Dropdown",
    "ExpandableSection",
    "Form",
    "FormInput",
    "Header",
    "HTMLBox",
    "Icon",
    "Image",
    "Link",
    "List",
    "Loader",
    "RadioGroup",
    "Section",
    "SubmitButton",
    "Table",
    "TextArea",
    "TextBox",
    "TimePicker",
    "Toggle",
})

# Maps every component type to the set of View Dictionary hierarchies
# it appears in (``UI Component``, ``FormView Component``,
# ``AWS-managed Views``, ``Customer-managed Views``). A type that
# appears in multiple hierarchies is valid in any of them; a type that
# appears only in ``FormView Component`` is only valid inside a
# ``Form`` ancestor.
COMPONENT_HIERARCHIES: dict[str, frozenset[str]] = {
    "Alert": frozenset({"UI Component"}),
    "Application": frozenset({"UI Component"}),
    "AttributeBar": frozenset({"UI Component"}),
    "AttributeSection": frozenset({"UI Component"}),
    "Button": frozenset({"UI Component"}),
    "ButtonGroup": frozenset({"UI Component"}),
    "Card": frozenset({"UI Component"}),
    "Cards": frozenset({"AWS-managed Views"}),
    "CheckboxGroup": frozenset({"FormView Component", "UI Component"}),
    "Confirmation": frozenset({"AWS-managed Views"}),
    "Container": frozenset({"UI Component"}),
    "DatePicker": frozenset({"FormView Component", "UI Component"}),
    "Detail": frozenset({"AWS-managed Views", "UI Component"}),
    "Dropdown": frozenset({"FormView Component", "UI Component"}),
    "ExpandableSection": frozenset({"UI Component"}),
    "Form": frozenset({"AWS-managed Views"}),
    "FormInput": frozenset({"FormView Component", "UI Component"}),
    "Header": frozenset({"UI Component"}),
    "HTMLBox": frozenset({"UI Component"}),
    "Icon": frozenset({"UI Component"}),
    "Image": frozenset({"UI Component"}),
    "Link": frozenset({"UI Component"}),
    "List": frozenset({"AWS-managed Views"}),
    "Loader": frozenset({"UI Component"}),
    "RadioGroup": frozenset({"FormView Component", "UI Component"}),
    "Section": frozenset({"UI Component"}),
    "SubmitButton": frozenset({"UI Component"}),
    "Table": frozenset({"UI Component"}),
    "TextArea": frozenset({"FormView Component", "UI Component"}),
    "TextBox": frozenset({"UI Component"}),
    "TimePicker": frozenset({"FormView Component", "UI Component"}),
    "Toggle": frozenset({"FormView Component", "UI Component"}),
}

# Convenience: types that only appear in the FormView hierarchy. The
# validator surfaces a warning when one of these is used outside a
# ``Form`` ancestor.
FORMVIEW_ONLY_TYPES: frozenset[str] = frozenset({

})

# Required props per component, snapshotted from each Storybook docs
# page's ArgsTable. The validator uses this to flag components that
# lack a required prop.
#
# Components that don't appear here had no ArgsTable on their docs
# page (e.g. umbrella reference entries, the standalone ``Image``
# story) — for those, ``validate_view_json`` only checks that ``Type``
# is recognized.
REQUIRED_PROPS: dict[str, frozenset[str]] = {
    "Alert": frozenset(),
    "Application": frozenset(),
    "AttributeBar": frozenset({"Attributes"}),
    "AttributeSection": frozenset({"Items"}),
    "Button": frozenset(),
    "ButtonGroup": frozenset({"Items"}),
    "Card": frozenset({"Id"}),
    "Cards": frozenset({"Cards"}),
    "CheckboxGroup": frozenset({"Label", "Name"}),
    "Confirmation": frozenset({"Next"}),
    "Container": frozenset(),
    "DatePicker": frozenset({"Label", "Name"}),
    "Detail": frozenset({"Sections"}),
    "Dropdown": frozenset({"Label", "Name", "Options"}),
    "ExpandableSection": frozenset(),
    "Form": frozenset({"Sections"}),
    "FormInput": frozenset({"Label", "Name"}),
    "Header": frozenset(),
    "HTMLBox": frozenset({"TemplateString"}),
    "Icon": frozenset(),
    "Link": frozenset(),
    "List": frozenset({"Items"}),
    "Loader": frozenset(),
    "RadioGroup": frozenset({"Label", "Name"}),
    "Section": frozenset(),
    "SubmitButton": frozenset({"Label"}),
    "Table": frozenset({"Name", "Items", "Columns"}),
    "TextArea": frozenset({"Label", "Name"}),
    "TextBox": frozenset(),
    "TimePicker": frozenset({"Label", "Name"}),
    "Toggle": frozenset({"Label", "Name"}),
}
