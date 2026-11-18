# Accessibility

We want everyone on a hiring team to be able to use ResumeAI, including people who use a keyboard, a screen reader, zoom or high contrast. We aim for [WCAG 2.2](https://www.w3.org/TR/WCAG22/) level AA.

## What we do today

- **Keyboard:** pages are built to work with the keyboard. Focus is visible, there is a "Skip to content" link, dialogs trap and return focus, and menus support the arrow keys and Escape.
- **Screen readers:** buttons and icons have accessible names. Scores are given as text, with a label, never by colour alone. Loading states and upload progress are announced.
- **Visual:** light and dark themes follow your system setting or your choice. Text and controls use theme colours chosen for contrast, and pages reflow on phones and when zoomed.
- **Motion:** animations are switched off when your system asks for reduced motion.
- **Alternatives:** you can drop resumes on a job page or pick them with the "Upload resumes" button.

## Known limitations

- **No formal audit yet.** We haven't run a full WCAG audit or tested with every screen reader. Our checks so far are built into development and code review.
- **AI-generated content** (interview questions, fact-checker answers, parsed resume text) comes from language models. Its wording may not always be plain or consistent.
- **Uploaded resumes** are shown as extracted text. Scanned image-only PDFs can't be read, so their content isn't available to anyone, including screen-reader users.

## Supported environments

Current versions of Chrome, Edge, Firefox and Safari on desktop, and Chrome and Safari on phones. We haven't yet tested systematically with screen readers or other assistive technology.

## Report a barrier

If something is hard or impossible to use, please [open an issue](https://github.com/Inward17/ResumeAI/issues/new?template=bug_report.yml) and choose any area that fits. Tell us:
- the page, and what you were trying to do
- your browser and any assistive technology (for example NVDA, VoiceOver or TalkBack)
- what happened, and what you expected

We treat accessibility barriers as bugs and aim to reply within a week.
