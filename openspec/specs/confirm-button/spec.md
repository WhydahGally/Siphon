## ADDED Requirements

### Requirement: ConfirmButton renders a single action button
`ConfirmButton.vue` SHALL accept a `label` prop (string) and render a single button displaying that label in its default state.

#### Scenario: Default state
- **WHEN** `ConfirmButton` is mounted
- **THEN** it SHALL display a single button with the text from the `label` prop

---

### Requirement: ConfirmButton splits into Confirm and Cancel on first click
When the user clicks the primary button, `ConfirmButton` SHALL transition to a confirming state displaying two buttons: one labelled from the `dangerLabel` prop (default "Confirm") and one labelled "Cancel", stacked vertically. No external event SHALL be emitted at this point.

#### Scenario: First click transitions to confirming state
- **WHEN** the user clicks the primary label button
- **THEN** the single button SHALL be replaced by two vertically stacked buttons: Confirm (top) and Cancel (bottom)

---

### Requirement: ConfirmButton emits confirm on second click
Clicking the Confirm button in the confirming state SHALL emit a `confirm` event and revert to the default state.

#### Scenario: Confirm clicked
- **WHEN** the user clicks the Confirm button
- **THEN** `ConfirmButton` SHALL emit `"confirm"` and return to default state

---

### Requirement: ConfirmButton reverts on Cancel
Clicking the Cancel button in the confirming state SHALL revert the component to its default state without emitting any event.

#### Scenario: Cancel clicked
- **WHEN** the user clicks the Cancel button
- **THEN** `ConfirmButton` SHALL return to the default single-button state and SHALL NOT emit `"confirm"`

---

### Requirement: ConfirmButton auto-reverts after 5 seconds
If the user clicks the primary button to enter confirming state but takes no action within 5 seconds, `ConfirmButton` SHALL automatically revert to its default state.

#### Scenario: Timeout with no action
- **WHEN** the user clicks the primary button and does not click Confirm or Cancel within 5 seconds
- **THEN** `ConfirmButton` SHALL revert to its default state without emitting any event
