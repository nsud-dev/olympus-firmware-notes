/* example_tg_renderer.c: an own c3d renderer that drives the built-in OpenVG library directly.
 *
 * Draws on the Tough Gear (TG) draw kind, which has no stock artwork: a translucent rounded panel, a filled circle
 * that orbits the centre by the angle in the UPDATE data, and a stroked arc that turns with it. Every vg* call goes through
 * c3d_vg.h, so the Olympus-ABI GCC puts each argument in the register the library expects.
 *
 * How it would be wired (runs in om-emu 2026-11-21, not tested on a camera; see notes docs/hardware/c3d-gpu.md sections 9 and 11):
 *   - c3d_exe calls the TG draw stub (E-M5 III 1.7: 0x60c27096) with a0 = the copied 4-byte UPDATE block, after
 *     setting the draw flag 0x6253c479. Replace the stub body with a call to tg_render.
 *   - tg_render must end with c3d_submit() (eglSwapBuffers on c3d's display and surface, as the stock submit
 *     0x60c2639f does), which lets c3d_exe report the frame as done.
 *   - The TG surface is 480 x 480; OpenVG's origin is the bottom-left corner.
 *
 * Build check: mn10300-elf-gcc -O2 -c example_tg_renderer.c (plain MN10300, no -mam33-2), then objdump -d and
 * compare the argument registers with the stock callers listed on the notes page.
 */
#include "c3d_vg.h"

static void set_colour(VGPaint p, float r, float g, float b, float a)
{
    VGfloat c[4];
    c[0] = r; c[1] = g; c[2] = b; c[3] = a;
    vgSetParameteri(p, VG_PAINT_TYPE, VG_PAINT_TYPE_COLOR);
    vgSetParameterfv(p, VG_PAINT_COLOR, 4, c);
}

static VGPath new_path(void)
{
    return vgCreatePath(VG_PATH_FORMAT_STANDARD, VG_PATH_DATATYPE_F, 1.0f, 0.0f, 0, 0, VG_PATH_CAPABILITY_ALL);
}

/* blk: the TG UPDATE block (4 bytes); here one float, an angle in degrees. Taking a float keeps the renderer free of
 * float arithmetic, which would need soft-float helpers (no linker here: see README). */
void tg_render(const VGfloat *blk)
{
    static const VGfloat clear[4] = { 0.0f, 0.0f, 0.0f, 0.0f };   /* fully transparent: live view shows through */
    VGfloat angle = blk[0];
    VGPaint paint = vgCreatePaint();
    VGPath panel = new_path(), dot = new_path(), arc = new_path();

    vgSetfv(VG_CLEAR_COLOR, 4, clear);
    vgClear(0, 0, 480, 480);
    vgSeti(VG_MATRIX_MODE, VG_MATRIX_PATH_USER_TO_SURFACE);

    /* translucent panel */
    vgLoadIdentity();
    vguRoundRect(panel, 40.0f, 40.0f, 400.0f, 400.0f, 32.0f, 32.0f);
    set_colour(paint, 0.0f, 0.0f, 0.0f, 0.5f);
    vgSetPaint(paint, VG_FILL_PATH);
    vgDrawPath(panel, VG_FILL_PATH);

    /* turn the drawing around the centre by the angle from the UPDATE data */
    vgTranslate(240.0f, 240.0f);
    vgRotate(angle);

    /* a circle that orbits the centre */
    vguEllipse(dot, 150.0f, 0.0f, 48.0f, 48.0f);
    set_colour(paint, 1.0f, 0.6f, 0.0f, 1.0f);
    vgSetPaint(paint, VG_FILL_PATH);
    vgDrawPath(dot, VG_FILL_PATH);

    /* a 90-degree stroked arc that turns with it */
    vguArc(arc, 0.0f, 0.0f, 300.0f, 300.0f, -45.0f, 90.0f, VGU_ARC_OPEN);
    vgSetf(VG_STROKE_LINE_WIDTH, 8.0f);
    set_colour(paint, 1.0f, 1.0f, 1.0f, 0.9f);
    vgSetPaint(paint, VG_STROKE_PATH);
    vgDrawPath(arc, VG_STROKE_PATH);

    vgDestroyPath(panel); vgDestroyPath(dot); vgDestroyPath(arc);
    vgDestroyPaint(paint);
    c3d_submit();
}
