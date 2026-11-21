#!/usr/bin/env python3
"""Make a C header that calls the camera's built-in EGL/OpenVG library by address.

usage: python3 -I c3d_proctable.py BLOCK0.bin > table.txt
       python3 -I c3d_vg_header.py table.txt [BODY] > c3d_vg.h

The prototypes are the standard EGL 1.4 / OpenVG 1.1 / VGU signatures (written from the public specifications) plus
the DMP extension calls whose arguments were read from the firmware's own callers. Calls with unknown arguments are
listed as addresses only. The header holds no firmware bytes: only function addresses (facts about the firmware).

The library's calling convention (read from its stock callers): arguments that are not pointers take d0, d1 and
pointers take a0, a1, each in argument order; what is left of either kind then fills the other kind's free registers
(eglInitialize: the third pointer goes in d0; vgClear: height and width go in a0, a1; vgCreatePath: scale and bias in
a0, a1); the rest goes on the stack from the caller's (4,sp). Floats travel as their 32-bit pattern. The Olympus-ABI
GCC alone would put a third integer on the stack, so each call is a static inline wrapper that reorders the
arguments into raw words (d-register words as unsigned int, a-register words as void *) for the toolchain's
class-by-class rule. Compile with the Olympus-ABI GCC (mn10300-elf GCC set to the camera's calling convention), plain MN10300, no -mam33-2.
"""
import sys

# name -> (return type, argument list). Standard signatures from the Khronos specifications.
P = {
 # EGL 1.4
 'eglGetError': ('EGLint', 'void'),
 'eglGetDisplay': ('EGLDisplay', 'EGLNativeDisplayType display_id'),
 'eglInitialize': ('EGLBoolean', 'EGLDisplay dpy, EGLint *major, EGLint *minor'),
 'eglTerminate': ('EGLBoolean', 'EGLDisplay dpy'),
 'eglQueryString': ('const char *', 'EGLDisplay dpy, EGLint name'),
 'eglGetConfigs': ('EGLBoolean', 'EGLDisplay dpy, EGLConfig *configs, EGLint config_size, EGLint *num_config'),
 'eglChooseConfig': ('EGLBoolean', 'EGLDisplay dpy, const EGLint *attrib_list, EGLConfig *configs, EGLint config_size, EGLint *num_config'),
 'eglGetConfigAttrib': ('EGLBoolean', 'EGLDisplay dpy, EGLConfig config, EGLint attribute, EGLint *value'),
 'eglCreateWindowSurface': ('EGLSurface', 'EGLDisplay dpy, EGLConfig config, EGLNativeWindowType win, const EGLint *attrib_list'),
 'eglCreatePbufferSurface': ('EGLSurface', 'EGLDisplay dpy, EGLConfig config, const EGLint *attrib_list'),
 'eglCreatePixmapSurface': ('EGLSurface', 'EGLDisplay dpy, EGLConfig config, EGLNativePixmapType pixmap, const EGLint *attrib_list'),
 'eglDestroySurface': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface surface'),
 'eglQuerySurface': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface surface, EGLint attribute, EGLint *value'),
 'eglBindAPI': ('EGLBoolean', 'EGLenum api'),
 'eglQueryAPI': ('EGLenum', 'void'),
 'eglWaitClient': ('EGLBoolean', 'void'),
 'eglReleaseThread': ('EGLBoolean', 'void'),
 'eglCreatePbufferFromClientBuffer': ('EGLSurface', 'EGLDisplay dpy, EGLenum buftype, EGLClientBuffer buffer, EGLConfig config, const EGLint *attrib_list'),
 'eglSurfaceAttrib': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface surface, EGLint attribute, EGLint value'),
 'eglBindTexImage': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface surface, EGLint buffer'),
 'eglReleaseTexImage': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface surface, EGLint buffer'),
 'eglSwapInterval': ('EGLBoolean', 'EGLDisplay dpy, EGLint interval'),
 'eglCreateContext': ('EGLContext', 'EGLDisplay dpy, EGLConfig config, EGLContext share_context, const EGLint *attrib_list'),
 'eglDestroyContext': ('EGLBoolean', 'EGLDisplay dpy, EGLContext ctx'),
 'eglMakeCurrent': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface draw, EGLSurface read, EGLContext ctx'),
 'eglGetCurrentContext': ('EGLContext', 'void'),
 'eglGetCurrentSurface': ('EGLSurface', 'EGLint readdraw'),
 'eglGetCurrentDisplay': ('EGLDisplay', 'void'),
 'eglQueryContext': ('EGLBoolean', 'EGLDisplay dpy, EGLContext ctx, EGLint attribute, EGLint *value'),
 'eglWaitGL': ('EGLBoolean', 'void'),
 'eglWaitNative': ('EGLBoolean', 'EGLint engine'),
 'eglSwapBuffers': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface surface'),
 'eglCopyBuffers': ('EGLBoolean', 'EGLDisplay dpy, EGLSurface surface, EGLNativePixmapType target'),
 'eglGetProcAddress': ('void *', 'const char *procname'),
 # OpenVG 1.1
 'vgGetError': ('VGErrorCode', 'void'),
 'vgFlush': ('void', 'void'),
 'vgFinish': ('void', 'void'),
 'vgSetf': ('void', 'VGParamType type, VGfloat value'),
 'vgSeti': ('void', 'VGParamType type, VGint value'),
 'vgSetfv': ('void', 'VGParamType type, VGint count, const VGfloat *values'),
 'vgSetiv': ('void', 'VGParamType type, VGint count, const VGint *values'),
 'vgGetf': ('VGfloat', 'VGParamType type'),
 'vgGeti': ('VGint', 'VGParamType type'),
 'vgGetVectorSize': ('VGint', 'VGParamType type'),
 'vgGetfv': ('void', 'VGParamType type, VGint count, VGfloat *values'),
 'vgGetiv': ('void', 'VGParamType type, VGint count, VGint *values'),
 'vgSetParameterf': ('void', 'VGHandle object, VGint paramType, VGfloat value'),
 'vgSetParameteri': ('void', 'VGHandle object, VGint paramType, VGint value'),
 'vgSetParameterfv': ('void', 'VGHandle object, VGint paramType, VGint count, const VGfloat *values'),
 'vgSetParameteriv': ('void', 'VGHandle object, VGint paramType, VGint count, const VGint *values'),
 'vgGetParameterf': ('VGfloat', 'VGHandle object, VGint paramType'),
 'vgGetParameteri': ('VGint', 'VGHandle object, VGint paramType'),
 'vgGetParameterVectorSize': ('VGint', 'VGHandle object, VGint paramType'),
 'vgGetParameterfv': ('void', 'VGHandle object, VGint paramType, VGint count, VGfloat *values'),
 'vgGetParameteriv': ('void', 'VGHandle object, VGint paramType, VGint count, VGint *values'),
 'vgLoadIdentity': ('void', 'void'),
 'vgLoadMatrix': ('void', 'const VGfloat *m'),
 'vgGetMatrix': ('void', 'VGfloat *m'),
 'vgMultMatrix': ('void', 'const VGfloat *m'),
 'vgTranslate': ('void', 'VGfloat tx, VGfloat ty'),
 'vgScale': ('void', 'VGfloat sx, VGfloat sy'),
 'vgShear': ('void', 'VGfloat shx, VGfloat shy'),
 'vgRotate': ('void', 'VGfloat angle'),
 'vgMask': ('void', 'VGHandle mask, VGMaskOperation operation, VGint x, VGint y, VGint width, VGint height'),
 'vgRenderToMask': ('void', 'VGPath path, VGbitfield paintModes, VGMaskOperation operation'),
 'vgCreateMaskLayer': ('VGMaskLayer', 'VGint width, VGint height'),
 'vgDestroyMaskLayer': ('void', 'VGMaskLayer maskLayer'),
 'vgFillMaskLayer': ('void', 'VGMaskLayer maskLayer, VGint x, VGint y, VGint width, VGint height, VGfloat value'),
 'vgCopyMask': ('void', 'VGMaskLayer maskLayer, VGint dx, VGint dy, VGint sx, VGint sy, VGint width, VGint height'),
 'vgClear': ('void', 'VGint x, VGint y, VGint width, VGint height'),
 'vgCreatePath': ('VGPath', 'VGint pathFormat, VGPathDatatype datatype, VGfloat scale, VGfloat bias, VGint segmentCapacityHint, VGint coordCapacityHint, VGbitfield capabilities'),
 'vgClearPath': ('void', 'VGPath path, VGbitfield capabilities'),
 'vgDestroyPath': ('void', 'VGPath path'),
 'vgRemovePathCapabilities': ('void', 'VGPath path, VGbitfield capabilities'),
 'vgGetPathCapabilities': ('VGbitfield', 'VGPath path'),
 'vgAppendPath': ('void', 'VGPath dstPath, VGPath srcPath'),
 'vgAppendPathData': ('void', 'VGPath dstPath, VGint numSegments, const VGubyte *pathSegments, const void *pathData'),
 'vgModifyPathCoords': ('void', 'VGPath dstPath, VGint startIndex, VGint numSegments, const void *pathData'),
 'vgTransformPath': ('void', 'VGPath dstPath, VGPath srcPath'),
 'vgInterpolatePath': ('VGboolean', 'VGPath dstPath, VGPath startPath, VGPath endPath, VGfloat amount'),
 'vgPathLength': ('VGfloat', 'VGPath path, VGint startSegment, VGint numSegments'),
 'vgPointAlongPath': ('void', 'VGPath path, VGint startSegment, VGint numSegments, VGfloat distance, VGfloat *x, VGfloat *y, VGfloat *tangentX, VGfloat *tangentY'),
 'vgPathBounds': ('void', 'VGPath path, VGfloat *minX, VGfloat *minY, VGfloat *width, VGfloat *height'),
 'vgPathTransformedBounds': ('void', 'VGPath path, VGfloat *minX, VGfloat *minY, VGfloat *width, VGfloat *height'),
 'vgDrawPath': ('void', 'VGPath path, VGbitfield paintModes'),
 'vgCreatePaint': ('VGPaint', 'void'),
 'vgDestroyPaint': ('void', 'VGPaint paint'),
 'vgSetPaint': ('void', 'VGPaint paint, VGbitfield paintModes'),
 'vgGetPaint': ('VGPaint', 'VGPaintMode paintMode'),
 'vgSetColor': ('void', 'VGPaint paint, VGuint rgba'),
 'vgGetColor': ('VGuint', 'VGPaint paint'),
 'vgPaintPattern': ('void', 'VGPaint paint, VGImage pattern'),
 'vgCreateImage': ('VGImage', 'VGImageFormat format, VGint width, VGint height, VGbitfield allowedQuality'),
 'vgDestroyImage': ('void', 'VGImage image'),
 'vgClearImage': ('void', 'VGImage image, VGint x, VGint y, VGint width, VGint height'),
 'vgImageSubData': ('void', 'VGImage image, const void *data, VGint dataStride, VGImageFormat dataFormat, VGint x, VGint y, VGint width, VGint height'),
 'vgGetImageSubData': ('void', 'VGImage image, void *data, VGint dataStride, VGImageFormat dataFormat, VGint x, VGint y, VGint width, VGint height'),
 'vgChildImage': ('VGImage', 'VGImage parent, VGint x, VGint y, VGint width, VGint height'),
 'vgGetParent': ('VGImage', 'VGImage image'),
 'vgCopyImage': ('void', 'VGImage dst, VGint dx, VGint dy, VGImage src, VGint sx, VGint sy, VGint width, VGint height, VGboolean dither'),
 'vgDrawImage': ('void', 'VGImage image'),
 'vgSetPixels': ('void', 'VGint dx, VGint dy, VGImage src, VGint sx, VGint sy, VGint width, VGint height'),
 'vgWritePixels': ('void', 'const void *data, VGint dataStride, VGImageFormat dataFormat, VGint dx, VGint dy, VGint width, VGint height'),
 'vgGetPixels': ('void', 'VGImage dst, VGint dx, VGint dy, VGint sx, VGint sy, VGint width, VGint height'),
 'vgReadPixels': ('void', 'void *data, VGint dataStride, VGImageFormat dataFormat, VGint sx, VGint sy, VGint width, VGint height'),
 'vgCopyPixels': ('void', 'VGint dx, VGint dy, VGint sx, VGint sy, VGint width, VGint height'),
 'vgCreateFont': ('VGFont', 'VGint glyphCapacityHint'),
 'vgDestroyFont': ('void', 'VGFont font'),
 'vgSetGlyphToPath': ('void', 'VGFont font, VGuint glyphIndex, VGPath path, VGboolean isHinted, const VGfloat *glyphOrigin, const VGfloat *escapement'),
 'vgSetGlyphToImage': ('void', 'VGFont font, VGuint glyphIndex, VGImage image, const VGfloat *glyphOrigin, const VGfloat *escapement'),
 'vgClearGlyph': ('void', 'VGFont font, VGuint glyphIndex'),
 'vgDrawGlyph': ('void', 'VGFont font, VGuint glyphIndex, VGbitfield paintModes, VGboolean allowAutoHinting'),
 'vgDrawGlyphs': ('void', 'VGFont font, VGint glyphCount, const VGuint *glyphIndices, const VGfloat *adjustments_x, const VGfloat *adjustments_y, VGbitfield paintModes, VGboolean allowAutoHinting'),
 'vgColorMatrix': ('void', 'VGImage dst, VGImage src, const VGfloat *matrix'),
 'vgConvolve': ('void', 'VGImage dst, VGImage src, VGint kernelWidth, VGint kernelHeight, VGint shiftX, VGint shiftY, const VGshort *kernel, VGfloat scale, VGfloat bias, VGTilingMode tilingMode'),
 'vgSeparableConvolve': ('void', 'VGImage dst, VGImage src, VGint kernelWidth, VGint kernelHeight, VGint shiftX, VGint shiftY, const VGshort *kernelX, const VGshort *kernelY, VGfloat scale, VGfloat bias, VGTilingMode tilingMode'),
 'vgGaussianBlur': ('void', 'VGImage dst, VGImage src, VGfloat stdDeviationX, VGfloat stdDeviationY, VGTilingMode tilingMode'),
 'vgLookup': ('void', 'VGImage dst, VGImage src, const VGubyte *redLUT, const VGubyte *greenLUT, const VGubyte *blueLUT, const VGubyte *alphaLUT, VGboolean outputLinear, VGboolean outputPremultiplied'),
 'vgLookupSingle': ('void', 'VGImage dst, VGImage src, const VGuint *lookupTable, VGImageChannel sourceChannel, VGboolean outputLinear, VGboolean outputPremultiplied'),
 'vgHardwareQuery': ('VGHardwareQueryResult', 'VGHardwareQueryType key, VGint setting'),
 'vgGetString': ('const VGubyte *', 'VGStringID name'),
 # VGU 1.1
 'vguLine': ('VGUErrorCode', 'VGPath path, VGfloat x0, VGfloat y0, VGfloat x1, VGfloat y1'),
 'vguPolygon': ('VGUErrorCode', 'VGPath path, const VGfloat *points, VGint count, VGboolean closed'),
 'vguRect': ('VGUErrorCode', 'VGPath path, VGfloat x, VGfloat y, VGfloat width, VGfloat height'),
 'vguRoundRect': ('VGUErrorCode', 'VGPath path, VGfloat x, VGfloat y, VGfloat width, VGfloat height, VGfloat arcWidth, VGfloat arcHeight'),
 'vguEllipse': ('VGUErrorCode', 'VGPath path, VGfloat cx, VGfloat cy, VGfloat width, VGfloat height'),
 'vguArc': ('VGUErrorCode', 'VGPath path, VGfloat x, VGfloat y, VGfloat width, VGfloat height, VGfloat startAngle, VGfloat angleExtent, VGUArcType arcType'),
 'vguComputeWarpQuadToSquare': ('VGUErrorCode', 'VGfloat sx0, VGfloat sy0, VGfloat sx1, VGfloat sy1, VGfloat sx2, VGfloat sy2, VGfloat sx3, VGfloat sy3, VGfloat *matrix'),
 'vguComputeWarpSquareToQuad': ('VGUErrorCode', 'VGfloat dx0, VGfloat dy0, VGfloat dx1, VGfloat dy1, VGfloat dx2, VGfloat dy2, VGfloat dx3, VGfloat dy3, VGfloat *matrix'),
 'vguComputeWarpQuadToQuad': ('VGUErrorCode', 'VGfloat dx0, VGfloat dy0, VGfloat dx1, VGfloat dy1, VGfloat dx2, VGfloat dy2, VGfloat dx3, VGfloat dy3, VGfloat sx0, VGfloat sy0, VGfloat sx1, VGfloat sy1, VGfloat sx2, VGfloat sy2, VGfloat sx3, VGfloat sy3, VGfloat *matrix'),
 # DMP extensions, arguments read from the stock callers (E-M5 III 1.7: 0x60c2751a, 0x60c27697)
 'vgCreateImageDataDMP': ('VGImage', 'VGImageFormat format, VGint width, VGint height, const void *data, VGint dataSize, VGbitfield allowedQuality'),
 'vgDrawSubImageDMP': ('void', 'VGImage image, VGint x, VGint y, VGint width, VGint height'),
}

PRE = r'''/* c3d_vg.h: call the built-in DMP EGL/OpenVG library of the Olympus %(body)s by address.
 * Generated by c3d_vg_header.py from the eglGetProcAddress table at %(table)s. Addresses only; no firmware bytes.
 *
 * Use only inside a c3d renderer (a c3d_exe draw command): that task owns the EGL display, surface and VG context
 * that every vg* call works on. End each frame with c3d_submit() below (eglSwapBuffers on c3d's display and surface).
 * Do not call the stock submit 0x60c2639f through a pointer: it has no prologue and must be entered by `call`. See the notes page
 * hardware/c3d-gpu.md, sections 2, 4b, 9 and 11.
 * Compile with the Olympus-ABI GCC as plain MN10300 (no -mam33-2).
 */
#ifndef C3D_VG_H
#define C3D_VG_H

typedef float VGfloat; typedef signed char VGbyte; typedef unsigned char VGubyte; typedef short VGshort;
typedef int VGint; typedef unsigned int VGuint; typedef unsigned int VGbitfield; typedef unsigned int VGboolean;
typedef VGuint VGHandle; typedef VGHandle VGPath, VGImage, VGMaskLayer, VGFont, VGPaint;
typedef int VGErrorCode, VGParamType, VGPathDatatype, VGMaskOperation, VGPaintMode, VGImageFormat, VGTilingMode,
    VGImageChannel, VGHardwareQueryType, VGHardwareQueryResult, VGStringID, VGUErrorCode, VGUArcType;
typedef int EGLint; typedef unsigned int EGLBoolean, EGLenum;
typedef void *EGLDisplay, *EGLConfig, *EGLSurface, *EGLContext, *EGLClientBuffer;
typedef void *EGLNativeDisplayType, *EGLNativeWindowType, *EGLNativePixmapType;

static inline unsigned int c3d_fbits(float f) { union { float f; unsigned int u; } x; x.f = f; return x.u; }

/* a few constants from the OpenVG 1.1 specification */
#define VG_STROKE_PATH 1
#define VG_FILL_PATH 2
#define VG_PATH_FORMAT_STANDARD 0
#define VG_PATH_DATATYPE_F 3
#define VG_PATH_CAPABILITY_ALL 0xfff
#define VG_MATRIX_MODE 0x1100
#define VG_CLEAR_COLOR 0x1121
#define VG_STROKE_LINE_WIDTH 0x1110
#define VG_MATRIX_PATH_USER_TO_SURFACE 0x1400
#define VG_MATRIX_IMAGE_USER_TO_SURFACE 0x1401
#define VG_PAINT_TYPE 0x1a00
#define VG_PAINT_COLOR 0x1a01
#define VG_PAINT_TYPE_COLOR 0x1b00
#define VG_CLOSE_PATH 0
#define VG_MOVE_TO_ABS 2
#define VG_LINE_TO_ABS 4
#define VG_QUAD_TO_ABS 10
#define VG_CUBIC_TO_ABS 12
#define VGU_ARC_OPEN 0xf100

'''

def split_args(args):
    if args.strip() == 'void':
        return []
    out = []
    for a in args.split(','):
        a = a.strip()
        k = max(a.rfind(' '), a.rfind('*'))
        out.append((a[:k + 1].strip(), a[k + 1:].strip()))
    return out


PTR_TYPES = {'EGLDisplay', 'EGLConfig', 'EGLSurface', 'EGLContext', 'EGLClientBuffer', 'EGLNativeDisplayType',
             'EGLNativeWindowType', 'EGLNativePixmapType'}


def is_ptr(t):
    return '*' in t or t.replace('const ', '') in PTR_TYPES


def assign(params):
    """Register (d0, d1, a0, a1) or None (stack) for each parameter, by the library's rule."""
    ptr = [is_ptr(t) for t, _ in params]
    reg = [None] * len(params)
    free = {'d': ['d0', 'd1'], 'a': ['a0', 'a1']}
    left = []
    for i, p in enumerate(ptr):
        own = 'a' if p else 'd'
        if free[own]:
            reg[i] = free[own].pop(0)
        else:
            left.append(i)
    for i in left:
        other = 'd' if ptr[i] else 'a'
        if free[other]:
            reg[i] = free[other].pop(0)
    return reg


def wrapper(name, ret, args, addr):
    params = split_args(args)
    reg = assign(params)
    order = sorted([i for i, r in enumerate(reg) if r], key=lambda i: reg[i]) + [i for i, r in enumerate(reg) if not r]
    proto, call = [], []
    for i in order:
        t, n = params[i]
        word = 'void *' if (reg[i] or '').startswith('a') else 'unsigned int'
        proto.append(word)
        if t in ('VGfloat',):
            v = f'c3d_fbits({n})'
        elif '*' in t:
            v = f'(unsigned int){n}'
        else:
            v = f'(unsigned int){n}'
        call.append(f'({word}){v}' if word == 'void *' else v)
    pl = ', '.join(proto) or 'void'
    r = '' if ret == 'void' else 'return '
    regs = ' '.join(f'{params[i][1]}={reg[i] or "stack"}' for i in range(len(params)))
    return (f'/* {regs} */\nstatic inline {ret} {name}({args})\n'
            f'{{ {r}(({ret} (*)({pl})){addr})({", ".join(call)}); }}\n')


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    body = a[1] if len(a) > 1 else 'E-M5 Mark III fw 1.7'
    rows = [l.split()[:3] for l in open(a[0]) if l.startswith('0x')]
    out = [PRE % {'body': body, 'table': rows[0][0]}]
    unknown = []
    for ta, fa, name in rows:
        out.append(f'#define {name}_ADDR {fa}\n')
    out.append('\n')
    for ta, fa, name in rows:
        if name in P:
            ret, args = P[name]
            out.append(wrapper(name, ret, args, fa))
        else:
            unknown.append(name)
    out.append('\n/* arguments not yet read (no stock caller), address only: ' + ', '.join(unknown) + ' */\n')
    out.append('\n/* E-M5 III 1.7: c3d\'s EGL display and window surface (notes docs/hardware/c3d-gpu.md section 11). Other bodies: change these. */\n'
               '#define C3D_EGL_DISPLAY (*(EGLDisplay *)0x6253c4a0)\n#define C3D_EGL_SURFACE (*(EGLSurface *)0x6253c4ac)\n'
               'static inline void c3d_submit(void) { eglSwapBuffers(C3D_EGL_DISPLAY, C3D_EGL_SURFACE); }\n')
    out.append('\n#endif\n')
    sys.stdout.write(''.join(out))


if __name__ == '__main__':
    main()
