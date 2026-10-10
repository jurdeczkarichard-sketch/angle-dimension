# Angle Dimension – an extension for IngeTrazo

Measures the angle between two lines that share a corner point and leaves a
permanent, labelled angle dimension in your drawing: two arms, an arc and the
angle in degrees.

**Version:** 1.0.0  **Licence:** MIT  **Author:** Ryszard Jurdeczka
**Requires:** IngeTrazo with extension API version 2 or newer
**Tested on:** Linux (MX Linux, IngeTrazo as a Flatpak)

## Install

1. In IngeTrazo choose **Extensions ▸ Open plugins folder**.
2. Copy `Angle_Dimension.py` into that folder.
3. Restart IngeTrazo.

You should now see **Draw angle dim** and an **Angle dim tools** sub-menu in
the Extensions menu.

> **Do not rename the file.** IngeTrazo stores each extension's data inside
> the drawing under the file's name. If you rename it, drawings saved earlier
> will not show their dimensions. Naming it back to `Angle_Dimension.py`
> brings them back.

## Use

**Extensions ▸ Draw angle dim** (Ctrl+Alt+A)

1. Click the **vertex** (the corner of the angle).
2. Click a point on the **first arm**.
3. Move the mouse – a live preview of the angle is shown.
4. Click a point on the **second arm**. The dimension is saved.

The tool stays active, so you can keep adding dimensions. Choose another tool
when you have finished.

**Extensions ▸ Angle dim tools**

| Command | Shortcut | What it does |
|---|---|---|
| Undo last angle dim | Ctrl+Alt+U | Cancels a half-finished dimension, otherwise removes the newest one |
| Delete angle dim | Ctrl+Alt+D | Then click on (or near) a dimension to delete it |
| Clear all angle dims | Ctrl+Alt+E | Removes every angle dimension (asks first) |
| About angle dim | Ctrl+Alt+I | Shows the version and how many dimensions the drawing has |

IngeTrazo's own **Ctrl+Z** also undoes adding or deleting a dimension.

## Where the dimensions are stored

Inside the drawing (`.igz`) itself, using IngeTrazo's extension storage. They
are saved when you save the drawing, belong to that drawing only, and appear
again when you open it. Adding or deleting a dimension counts as an edit, so
the drawing becomes "unsaved". Nothing is written anywhere else.

## Uninstall

Remove `Angle_Dimension.py` from the plugins folder and restart. Drawings
still open normally; the stored dimension data stays in them, harmlessly, and
reappears if you reinstall the extension.

## Known limitations

- Only tested on Linux so far.
- If a shortcut clashes with another IngeTrazo shortcut it may not fire; the
  menu item still works.
- Written against extension API version 2. On an older IngeTrazo it shows a
  message and does nothing.

## Licence

MIT – see the licence text at the top of `Angle_Dimension.py`.
