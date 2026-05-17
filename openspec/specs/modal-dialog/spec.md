## ADDED Requirements

### Requirement: Reusable ModalDialog component with slots
The system SHALL provide a `ModalDialog.vue` component that renders a centered overlay modal using Vue Teleport. The component SHALL accept named slots: `header`, `body`, and `actions`. It SHALL accept props: `maxWidth` (string, default `"520px"`), `closeOnOverlay` (boolean, default `true`), and `show` (boolean, required).

#### Scenario: Modal renders when show is true
- **WHEN** `show` prop is `true`
- **THEN** the modal overlay and content SHALL be visible in the DOM via Teleport to `body`

#### Scenario: Modal hidden when show is false
- **WHEN** `show` prop is `false`
- **THEN** no modal overlay or content SHALL be rendered in the DOM

#### Scenario: Close on overlay click
- **WHEN** `closeOnOverlay` is `true` AND user clicks the overlay background
- **THEN** the component SHALL emit a `close` event

#### Scenario: Close button always present
- **WHEN** the modal is visible
- **THEN** a ✕ close button SHALL be present in the top-right corner and SHALL emit `close` on click

#### Scenario: Max-width applied to content
- **WHEN** `maxWidth` is set to `"520px"`
- **THEN** the modal content container SHALL have `max-width: 520px`

### Requirement: ModalDialog is responsive on mobile
The modal SHALL be usable on viewports as narrow as 320px. On screens below 600px, the modal content SHALL expand to full width with 16px horizontal padding. Action buttons SHALL stack vertically on narrow viewports.

#### Scenario: Desktop layout
- **WHEN** viewport width is >= 600px
- **THEN** the modal content SHALL be centered with the configured `maxWidth` and action buttons SHALL be displayed inline (row)

#### Scenario: Mobile layout
- **WHEN** viewport width is < 600px
- **THEN** the modal content SHALL be full-width with 16px side padding and action buttons SHALL stack vertically with full width

### Requirement: ModalDialog traps focus for accessibility
When the modal is open, keyboard focus SHALL be trapped within the modal. Pressing Escape SHALL emit a `close` event.

#### Scenario: Escape key closes modal
- **WHEN** the modal is visible AND user presses Escape
- **THEN** the component SHALL emit a `close` event

#### Scenario: Tab cycles within modal
- **WHEN** the modal is visible AND user presses Tab on the last focusable element
- **THEN** focus SHALL cycle back to the first focusable element within the modal
