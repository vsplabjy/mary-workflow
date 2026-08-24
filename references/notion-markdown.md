# Notion-Flavored Markdown Reference

Use this as the page-body syntax reference. The active Notion MCP tool schema remains
authoritative when it documents a different wire format.

## Basic Blocks

| Block | Syntax |
| --- | --- |
| Paragraph | Plain text separated by blank lines |
| Heading | `## Heading` / `### Heading` in page bodies |
| Bullets | `- Item`, with child blocks indented by one Tab |
| Ordered list | `1. Item`, with related media/code indented as child content |
| To-do | `- [ ] Task` / `- [x] Task` |
| Quote | `> Text`; use `<br>` for line breaks in one quote |
| Divider | `---` between major sections only |
| Code | Fenced block with a language identifier |
| Equation | `$$` delimiters on their own lines |
| Table of contents | `<table_of_contents/>` |

Add a supported block color attribute on the block's first line, for example
`{color="blue_bg"}`.

## Inline Rich Text

- Bold: `**text**`; italic: `*text*`; strike: `~~text~~`.
- Underline: `<span underline="true">text</span>`.
- Inline code: backticks, only for identifiers, commands, paths, and code tokens.
- Link: `[label](URL)`.
- Inline color: `<span color="red">text</span>`; use sparingly.
- Inline line break: `<br>`.
- Inline equation: a dollar sign, a backtick-delimited LaTeX expression, then a dollar
  sign. Do not escape the dollar signs.

## Advanced Blocks

```text
<callout icon="!" color="yellow_bg">
	**Warning**
	- Child blocks use one Tab of indentation.
</callout>

<details color="gray_bg">
<summary>Details</summary>
	Long supporting content
</details>

## Toggle heading {toggle="true" color="gray_bg"}
	Nested content

<columns>
	<column ratio="50">Left</column>
	<column ratio="50">Right</column>
</columns>

<table fit-page-width="true" header-row="true" header-column="false">
	<colgroup><col color="gray"><col></colgroup>
	<tr color="gray_bg"><td>Header</td><td>Header</td></tr>
	<tr><td>Value</td><td>Value</td></tr>
</table>
```

Table cells contain inline rich text only. Do not put headings, lists, images, code
blocks, or complex equations in cells. Use `<br>` rather than a literal block break.
The API cannot merge cells; tell the user when UI-only merging is needed.

## Media and Structural Objects

```text
![Figure 1 - Caption](URL)
<pdf src="URL">Source PDF</pdf>
<file src="URL">Attachment</file>
<embed src="URL">HTML artifact</embed>
<page url="URL">Real child page</page>
<synced_block>...</synced_block>
```

`<page>` represents real hierarchy. Removing it or replacing it with a mention can move
or detach the child. Preserve fetched `<page>`, `<database>`, synced, embed, attachment,
and unknown blocks exactly unless the user explicitly requests that structural change.

## Mentions

```text
<mention-page url="URL">Page title</mention-page>
<mention-database url="URL"/>
<mention-user url="URL"/>
<mention-date start="2026-09-20" startTime="23:59" timeZone="Asia/Shanghai"/>
```

A mention is an inline reference and does not change hierarchy.

## Colors

Text colors: `gray brown orange yellow green blue purple pink red`.
Background colors use the same name plus `_bg`.

## Common Errors

- Repeating the page title as H1 in the body.
- Putting block content or complex math inside a table cell.
- Writing several `>` lines when one quote with `<br>` is intended.
- Omitting a code language.
- Guessing a media/file URL.
- Replacing a child `<page>` with `<mention-page>`.
- Leaving Mermaid node labels with special characters unquoted.
