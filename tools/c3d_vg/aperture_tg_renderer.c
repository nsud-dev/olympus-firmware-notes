/* aperture_tg_renderer.c: a second own c3d renderer, made for the showcase pictures of the notes.
 *
 * Draws a lens-style dial on the Tough Gear (TG) kind: a smoked disc, six translucent cubic-curve blades in rainbow
 * colours over live view, a ring of 60 ticks, three arcs turning the other way, an orbiting dot and a centre hub. Every
 * shape turns with the angle in the UPDATE data. Same wiring and rules as example_tg_renderer.c (notes
 * docs/hardware/c3d-gpu.md sections 9 and 11): end with c3d_submit(), surface 480 x 480 with the origin bottom-left.
 *
 * No float arithmetic (it would need soft-float helpers, and elfload has no libgcc): every number is a constant or the
 * UPDATE angle, and repeats are made with the matrix (vgRotate by a constant step) instead of computed coordinates.
 * The counter-rotation uses a mirror (scale -1, rotate, scale -1) rather than negating the angle.
 *
 * Runs in om-emu with the c3dvg.mjs stand-in (2026-11-21); not tested on a camera.
 */
#include "c3d_vg.h"

static const VGubyte blade_segs[] = { VG_MOVE_TO_ABS, VG_CUBIC_TO_ABS, VG_CUBIC_TO_ABS, VG_CLOSE_PATH };
static const VGfloat blade_xy[] = { 20.0f, -10.0f,
                                    100.0f, -80.0f, 210.0f, 0.0f, 120.0f, 160.0f,
                                    110.0f, 70.0f, 70.0f, 15.0f, 20.0f, -10.0f };
static const VGubyte tick_segs[] = { VG_MOVE_TO_ABS, VG_LINE_TO_ABS };
static const VGfloat tick_short[] = { 182.0f, 0.0f, 192.0f, 0.0f };
static const VGfloat tick_long[] = { 174.0f, 0.0f, 196.0f, 0.0f };
static const VGfloat blade_rgba[6][4] = {
    { 1.00f, 0.25f, 0.35f, 0.55f }, { 1.00f, 0.65f, 0.10f, 0.55f }, { 0.95f, 0.95f, 0.20f, 0.55f },
    { 0.20f, 0.90f, 0.45f, 0.55f }, { 0.15f, 0.70f, 1.00f, 0.55f }, { 0.65f, 0.35f, 1.00f, 0.55f } };
static const VGfloat clear[4] = { 0.0f, 0.0f, 0.0f, 0.0f };

static void set_colour(VGPaint p, const VGfloat *c)
{
    vgSetParameteri(p, VG_PAINT_TYPE, VG_PAINT_TYPE_COLOR);
    vgSetParameterfv(p, VG_PAINT_COLOR, 4, c);
}

static VGPath new_path(void)
{
    return vgCreatePath(VG_PATH_FORMAT_STANDARD, VG_PATH_DATATYPE_F, 1.0f, 0.0f, 0, 0, VG_PATH_CAPABILITY_ALL);
}

static void centre(void)
{
    vgLoadIdentity();
    vgTranslate(240.0f, 240.0f);
}

void tg_render(const VGfloat *blk)
{
    static const VGfloat smoke[4] = { 0.02f, 0.03f, 0.08f, 0.45f };
    static const VGfloat white[4] = { 1.0f, 1.0f, 1.0f, 0.95f };
    static const VGfloat soft[4] = { 1.0f, 1.0f, 1.0f, 0.55f };
    static const VGfloat cyan[4] = { 0.35f, 0.85f, 1.0f, 0.85f };
    static const VGfloat amber[4] = { 1.0f, 0.62f, 0.05f, 1.0f };
    VGfloat angle = blk[0];
    VGPaint paint = vgCreatePaint();
    VGPath disc = new_path(), blade = new_path(), ts = new_path(), tl = new_path(), ring = new_path(),
           arc = new_path(), dot = new_path(), hub = new_path();
    int i;

    vgSetfv(VG_CLEAR_COLOR, 4, clear);
    vgClear(0, 0, 480, 480);
    vgSeti(VG_MATRIX_MODE, VG_MATRIX_PATH_USER_TO_SURFACE);

    /* smoked disc behind everything */
    centre();
    vguEllipse(disc, 0.0f, 0.0f, 440.0f, 440.0f);
    set_colour(paint, smoke);
    vgSetPaint(paint, VG_FILL_PATH);
    vgDrawPath(disc, VG_FILL_PATH);

    /* six blades, 60 degrees apart, all turned by the UPDATE angle */
    vgAppendPathData(blade, 4, blade_segs, blade_xy);
    centre();
    vgRotate(angle);
    for (i = 0; i < 6; i++) {
        set_colour(paint, blade_rgba[i]);
        vgSetPaint(paint, VG_FILL_PATH);
        vgDrawPath(blade, VG_FILL_PATH);
        vgRotate(60.0f);
    }

    /* outer ring and 60 ticks (every fifth one long) */
    centre();
    vguEllipse(ring, 0.0f, 0.0f, 408.0f, 408.0f);
    vgSetf(VG_STROKE_LINE_WIDTH, 5.0f);
    set_colour(paint, white);
    vgSetPaint(paint, VG_STROKE_PATH);
    vgDrawPath(ring, VG_STROKE_PATH);
    vgAppendPathData(ts, 2, tick_segs, tick_short);
    vgAppendPathData(tl, 2, tick_segs, tick_long);
    vgSetf(VG_STROKE_LINE_WIDTH, 3.0f);
    vgRotate(angle);
    for (i = 0; i < 60; i++) {
        set_colour(paint, (i % 5) ? soft : white);
        vgSetPaint(paint, VG_STROKE_PATH);
        vgDrawPath((i % 5) ? ts : tl, VG_STROKE_PATH);
        vgRotate(6.0f);
    }

    /* three arcs turning the other way: mirror, rotate, mirror */
    centre();
    vgScale(-1.0f, 1.0f);
    vgRotate(angle);
    vgScale(-1.0f, 1.0f);
    vguArc(arc, 0.0f, 0.0f, 440.0f, 440.0f, 0.0f, 70.0f, VGU_ARC_OPEN);
    vgSetf(VG_STROKE_LINE_WIDTH, 9.0f);
    set_colour(paint, cyan);
    vgSetPaint(paint, VG_STROKE_PATH);
    for (i = 0; i < 3; i++) {
        vgDrawPath(arc, VG_STROKE_PATH);
        vgRotate(120.0f);
    }

    /* a dot orbiting on the ring, and the hub */
    centre();
    vgRotate(angle);
    vguEllipse(dot, 204.0f, 0.0f, 26.0f, 26.0f);
    set_colour(paint, amber);
    vgSetPaint(paint, VG_FILL_PATH);
    vgDrawPath(dot, VG_FILL_PATH);
    centre();
    vguEllipse(hub, 0.0f, 0.0f, 44.0f, 44.0f);
    set_colour(paint, white);
    vgSetPaint(paint, VG_FILL_PATH);
    vgDrawPath(hub, VG_FILL_PATH);

    vgDestroyPath(disc); vgDestroyPath(blade); vgDestroyPath(ts); vgDestroyPath(tl); vgDestroyPath(ring);
    vgDestroyPath(arc); vgDestroyPath(dot); vgDestroyPath(hub);
    vgDestroyPaint(paint);
    c3d_submit();
}
