from pathlib import Path
import subprocess

ROOT = Path('.')


def replace_once(path_str: str, old_lf: str, new_lf: str, label: str) -> None:
    path = ROOT / path_str
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'
    old = old_lf.replace('\n', nl)
    new = new_lf.replace('\n', nl)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{label}: anchor count={count}, expected 1')
    path.write_bytes(text.replace(old, new, 1).encode('utf-8'))


def replace_exact_count(path_str: str, old_lf: str, new_lf: str, expected: int, label: str) -> None:
    path = ROOT / path_str
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'
    old = old_lf.replace('\n', nl)
    new = new_lf.replace('\n', nl)
    count = text.count(old)
    if count != expected:
        raise RuntimeError(f'{label}: anchor count={count}, expected {expected}')
    path.write_bytes(text.replace(old, new).encode('utf-8'))


# Keep existing numeric values stable; FSR is appended so older configs remain valid.
replace_once(
    'src/config/CemuConfig.h',
    '''enum UpscalingFilter
{
\tkLinearFilter,
\tkBicubicFilter,
\tkBicubicHermiteFilter,
\tkNearestNeighborFilter,
};''',
    '''enum UpscalingFilter
{
\tkLinearFilter,
\tkBicubicFilter,
\tkBicubicHermiteFilter,
\tkNearestNeighborFilter,
\tkFidelityFXFSREasuFilter,
};''',
    'UpscalingFilter enum',
)

replace_once(
    'src/gui/wxgui/GeneralSettings2.cpp',
    '''\t\twxString choices[] = { _("Bilinear"), _("Bicubic"), _("Hermite"), _("Nearest Neighbor") };
\t\tm_upscale_filter = new wxRadioBox(graphics_panel, wxID_ANY, _("Upscale filter"), wxDefaultPosition, wxDefaultSize, std::size(choices), choices, 5, wxRA_SPECIFY_COLS);''',
    '''\t\twxString upscale_choices[] = { _("Bilinear"), _("Bicubic"), _("Hermite"), _("Nearest Neighbor"), _("FidelityFX FSR (EASU)") };
\t\tm_upscale_filter = new wxRadioBox(graphics_panel, wxID_ANY, _("Upscale filter"), wxDefaultPosition, wxDefaultSize, std::size(upscale_choices), upscale_choices, 5, wxRA_SPECIFY_COLS);''',
    'upscale filter choices',
)

replace_once(
    'src/gui/wxgui/GeneralSettings2.cpp',
    '''\t\tm_downscale_filter = new wxRadioBox(graphics_panel, wxID_ANY, _("Downscale filter"), wxDefaultPosition, wxDefaultSize, std::size(choices), choices, 5, wxRA_SPECIFY_COLS);''',
    '''\t\twxString downscale_choices[] = { _("Bilinear"), _("Bicubic"), _("Hermite"), _("Nearest Neighbor") };
\t\tm_downscale_filter = new wxRadioBox(graphics_panel, wxID_ANY, _("Downscale filter"), wxDefaultPosition, wxDefaultSize, std::size(downscale_choices), downscale_choices, 5, wxRA_SPECIFY_COLS);''',
    'downscale filter choices',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.h',
    '''\tstatic RendererOutputShader* s_hermit_shader;
\tstatic RendererOutputShader* s_hermit_shader_ud;

\tstatic std::string GetOpenGlVertexSource(bool render_upside_down);''',
    '''\tstatic RendererOutputShader* s_hermit_shader;
\tstatic RendererOutputShader* s_hermit_shader_ud;

\tstatic RendererOutputShader* s_fsr_easu_shader;
\tstatic RendererOutputShader* s_fsr_easu_shader_ud;

\tstatic std::string GetOpenGlVertexSource(bool render_upside_down);''',
    'FSR shader pointers declaration',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.h',
    '''\tstatic const std::string s_copy_shader_source;
\tstatic const std::string s_bicubic_shader_source;
\tstatic const std::string s_hermite_shader_source;

\tstatic const std::string s_bicubic_shader_source_vk;''',
    '''\tstatic const std::string s_copy_shader_source;
\tstatic const std::string s_bicubic_shader_source;
\tstatic const std::string s_hermite_shader_source;
\tstatic const std::string s_fsr_easu_shader_source;

\tstatic const std::string s_bicubic_shader_source_vk;''',
    'FSR shader source declaration',
)

fsr_source = r'''
// AMD FidelityFX Super Resolution 1.0 - EASU spatial upscaling stage.
// Ported to Cemu's output-shader interface from AMD's FSR 1 reference.
// Copyright (c) 2021 Advanced Micro Devices, Inc. All rights reserved.
// Permission is hereby granted, free of charge, to any person obtaining a copy
// of this software and associated documentation files (the "Software"), to deal
// in the Software without restriction, including without limitation the rights
// to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
// copies of the Software, and to permit persons to whom the Software is
// furnished to do so, subject to the following conditions:
// The above copyright notice and this permission notice shall be included in
// all copies or substantial portions of the Software.
// THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
// IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
// FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
// AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
// LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
// OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
// THE SOFTWARE.

void fsrEasuSet(inout vec2 dir, inout float len, float w,
                float lA, float lB, float lC, float lD, float lE)
{
    float dc = lD - lC;
    float cb = lC - lB;
    float lenX = max(abs(dc), abs(cb));
    float dirX = lD - lB;
    dir.x += dirX * w;
    lenX = (lenX > 1.0e-8) ? clamp(abs(dirX) / lenX, 0.0, 1.0) : 0.0;
    len += lenX * lenX * w;

    float ec = lE - lC;
    float ca = lC - lA;
    float lenY = max(abs(ec), abs(ca));
    float dirY = lE - lA;
    dir.y += dirY * w;
    lenY = (lenY > 1.0e-8) ? clamp(abs(dirY) / lenY, 0.0, 1.0) : 0.0;
    len += lenY * lenY * w;
}

void fsrEasuTap(inout vec3 accumColor, inout float accumWeight,
                vec2 offset, vec2 dir, vec2 len, float lob, float clp, vec3 color)
{
    vec2 v;
    v.x = offset.x * dir.x + offset.y * dir.y;
    v.y = offset.x * -dir.y + offset.y * dir.x;
    v *= len;

    float d2 = min(dot(v, v), clp);
    float wB = (2.0 / 5.0) * d2 - 1.0;
    float wA = lob * d2 - 1.0;
    wB *= wB;
    wA *= wA;
    wB = (25.0 / 16.0) * wB - (25.0 / 16.0 - 1.0);
    float w = wB * wA;

    accumColor += color * w;
    accumWeight += w;
}

void outputShader()
{
    vec2 inputSize = max(textureSrcResolution, vec2(1.0));
    vec2 outputSize = max(outputResolution, vec2(1.0));
    vec2 invInput = 1.0 / inputSize;

    // FsrEasuCon() evaluated in-shader because Cemu already provides both sizes.
    vec4 con0 = vec4(inputSize / outputSize,
                     0.5 * inputSize / outputSize - vec2(0.5));
    vec4 con1 = vec4(invInput.x, invInput.y, invInput.x, -invInput.y);
    vec4 con2 = vec4(-invInput.x, 2.0 * invInput.y,
                      invInput.x, 2.0 * invInput.y);
    vec4 con3 = vec4(0.0, 4.0 * invInput.y, 0.0, 0.0);

    vec2 ip = floor(clamp(passUV * outputSize, vec2(0.0), outputSize - vec2(1.0)));
    vec2 pp = ip * con0.xy + con0.zw;
    vec2 fp = floor(pp);
    pp -= fp;

    vec2 p0 = fp * con1.xy + con1.zw;
    vec2 p1 = p0 + con2.xy;
    vec2 p2 = p0 + con2.zw;
    vec2 p3 = p0 + con3.xy;

    vec4 bczzR = textureGather(textureSrc, p0, 0);
    vec4 bczzG = textureGather(textureSrc, p0, 1);
    vec4 bczzB = textureGather(textureSrc, p0, 2);
    vec4 ijfeR = textureGather(textureSrc, p1, 0);
    vec4 ijfeG = textureGather(textureSrc, p1, 1);
    vec4 ijfeB = textureGather(textureSrc, p1, 2);
    vec4 klhgR = textureGather(textureSrc, p2, 0);
    vec4 klhgG = textureGather(textureSrc, p2, 1);
    vec4 klhgB = textureGather(textureSrc, p2, 2);
    vec4 zzonR = textureGather(textureSrc, p3, 0);
    vec4 zzonG = textureGather(textureSrc, p3, 1);
    vec4 zzonB = textureGather(textureSrc, p3, 2);

    vec4 bczzL = bczzB * 0.5 + (bczzR * 0.5 + bczzG);
    vec4 ijfeL = ijfeB * 0.5 + (ijfeR * 0.5 + ijfeG);
    vec4 klhgL = klhgB * 0.5 + (klhgR * 0.5 + klhgG);
    vec4 zzonL = zzonB * 0.5 + (zzonR * 0.5 + zzonG);

    float bL = bczzL.x;
    float cL = bczzL.y;
    float iL = ijfeL.x;
    float jL = ijfeL.y;
    float fL = ijfeL.z;
    float eL = ijfeL.w;
    float kL = klhgL.x;
    float lL = klhgL.y;
    float hL = klhgL.z;
    float gL = klhgL.w;
    float oL = zzonL.z;
    float nL = zzonL.w;

    vec2 dir = vec2(0.0);
    float len = 0.0;
    fsrEasuSet(dir, len, (1.0 - pp.x) * (1.0 - pp.y), bL, eL, fL, gL, jL);
    fsrEasuSet(dir, len, pp.x * (1.0 - pp.y),         cL, fL, gL, hL, kL);
    fsrEasuSet(dir, len, (1.0 - pp.x) * pp.y,         fL, iL, jL, kL, nL);
    fsrEasuSet(dir, len, pp.x * pp.y,                 gL, jL, kL, lL, oL);

    float dirLen2 = dot(dir, dir);
    if (dirLen2 < (1.0 / 32768.0))
        dir = vec2(1.0, 0.0);
    else
        dir *= inversesqrt(dirLen2);

    len = 0.5 * len;
    len *= len;
    float stretch = 1.0 / max(max(abs(dir.x), abs(dir.y)), 1.0e-8);
    vec2 len2 = vec2(1.0 + (stretch - 1.0) * len,
                     1.0 - 0.5 * len);
    float lob = 0.5 + ((1.0 / 4.0 - 0.04) - 0.5) * len;
    float clp = 1.0 / lob;

    vec3 f = vec3(ijfeR.z, ijfeG.z, ijfeB.z);
    vec3 g = vec3(klhgR.w, klhgG.w, klhgB.w);
    vec3 j = vec3(ijfeR.y, ijfeG.y, ijfeB.y);
    vec3 k = vec3(klhgR.x, klhgG.x, klhgB.x);
    vec3 min4 = min(min(f, g), min(j, k));
    vec3 max4 = max(max(f, g), max(j, k));

    vec3 accumColor = vec3(0.0);
    float accumWeight = 0.0;
    fsrEasuTap(accumColor, accumWeight, vec2( 0.0, -1.0) - pp, dir, len2, lob, clp, vec3(bczzR.x, bczzG.x, bczzB.x));
    fsrEasuTap(accumColor, accumWeight, vec2( 1.0, -1.0) - pp, dir, len2, lob, clp, vec3(bczzR.y, bczzG.y, bczzB.y));
    fsrEasuTap(accumColor, accumWeight, vec2(-1.0,  1.0) - pp, dir, len2, lob, clp, vec3(ijfeR.x, ijfeG.x, ijfeB.x));
    fsrEasuTap(accumColor, accumWeight, vec2( 0.0,  1.0) - pp, dir, len2, lob, clp, vec3(ijfeR.y, ijfeG.y, ijfeB.y));
    fsrEasuTap(accumColor, accumWeight, vec2( 0.0,  0.0) - pp, dir, len2, lob, clp, vec3(ijfeR.z, ijfeG.z, ijfeB.z));
    fsrEasuTap(accumColor, accumWeight, vec2(-1.0,  0.0) - pp, dir, len2, lob, clp, vec3(ijfeR.w, ijfeG.w, ijfeB.w));
    fsrEasuTap(accumColor, accumWeight, vec2( 1.0,  1.0) - pp, dir, len2, lob, clp, vec3(klhgR.x, klhgG.x, klhgB.x));
    fsrEasuTap(accumColor, accumWeight, vec2( 2.0,  1.0) - pp, dir, len2, lob, clp, vec3(klhgR.y, klhgG.y, klhgB.y));
    fsrEasuTap(accumColor, accumWeight, vec2( 2.0,  0.0) - pp, dir, len2, lob, clp, vec3(klhgR.z, klhgG.z, klhgB.z));
    fsrEasuTap(accumColor, accumWeight, vec2( 1.0,  0.0) - pp, dir, len2, lob, clp, vec3(klhgR.w, klhgG.w, klhgB.w));
    fsrEasuTap(accumColor, accumWeight, vec2( 1.0,  2.0) - pp, dir, len2, lob, clp, vec3(zzonR.z, zzonG.z, zzonB.z));
    fsrEasuTap(accumColor, accumWeight, vec2( 0.0,  2.0) - pp, dir, len2, lob, clp, vec3(zzonR.w, zzonG.w, zzonB.w));

    vec3 result = accumColor / max(accumWeight, 1.0e-8);
    colorOut0 = vec4(clamp(result, min4, max4), 1.0);
}
'''.strip('\n')

cpp_insert = (
    'const std::string RendererOutputShader::s_fsr_easu_shader_source =\n'
    'R"(\n' + fsr_source + '\n)";\n\n'
    'RendererOutputShader* RendererOutputShader::s_copy_shader;'
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    'RendererOutputShader* RendererOutputShader::s_copy_shader;',
    cpp_insert,
    'FSR EASU GLSL source',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''RendererOutputShader* RendererOutputShader::s_hermit_shader;
RendererOutputShader* RendererOutputShader::s_hermit_shader_ud;

std::string RendererOutputShader::GetOpenGlVertexSource(bool render_upside_down)''',
    '''RendererOutputShader* RendererOutputShader::s_hermit_shader;
RendererOutputShader* RendererOutputShader::s_hermit_shader_ud;

RendererOutputShader* RendererOutputShader::s_fsr_easu_shader;
RendererOutputShader* RendererOutputShader::s_fsr_easu_shader_ud;

std::string RendererOutputShader::GetOpenGlVertexSource(bool render_upside_down)''',
    'FSR shader pointers definition',
)

replace_exact_count(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''    \ts_hermit_shader = new RendererOutputShader(vertex_source, s_hermite_shader_source);
    \ts_hermit_shader_ud = new RendererOutputShader(vertex_source_ud, s_hermite_shader_source);
\t\tbreak;''',
    '''    \ts_hermit_shader = new RendererOutputShader(vertex_source, s_hermite_shader_source);
    \ts_hermit_shader_ud = new RendererOutputShader(vertex_source_ud, s_hermite_shader_source);

    \ts_fsr_easu_shader = new RendererOutputShader(vertex_source, s_fsr_easu_shader_source);
    \ts_fsr_easu_shader_ud = new RendererOutputShader(vertex_source_ud, s_fsr_easu_shader_source);
\t\tbreak;''',
    2,
    'OpenGL/Vulkan FSR init',
)

replace_once(
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    '''\tdelete s_hermit_shader;
\tdelete s_hermit_shader_ud;
}''',
    '''\tdelete s_hermit_shader;
\tdelete s_hermit_shader_ud;

\tdelete s_fsr_easu_shader;
\tdelete s_fsr_easu_shader_ud;
}''',
    'FSR shutdown',
)

replace_once(
    'src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp',
    '''\t\telse if (scaling_filter == kNearestNeighborFilter)
\t\t{
\t\t\tif (renderUpsideDown)
\t\t\t\tshader = RendererOutputShader::s_copy_shader_ud;
\t\t\telse
\t\t\t\tshader = RendererOutputShader::s_copy_shader;''',
    '''\t\telse if (scaling_filter == kFidelityFXFSREasuFilter)
\t\t{
\t\t\t// FSR EASU is an upscaler. If a config manually selects it for
\t\t\t// downscaling, retain Cemu's normal linear path instead.
\t\t\tif (downscaling)
\t\t\t{
\t\t\t\tif (renderUpsideDown)
\t\t\t\t\tshader = RendererOutputShader::s_copy_shader_ud;
\t\t\t\telse
\t\t\t\t\tshader = RendererOutputShader::s_copy_shader;
\t\t\t}
\t\t\telse
\t\t\t{
\t\t\t\tif (renderUpsideDown)
\t\t\t\t\tshader = RendererOutputShader::s_fsr_easu_shader_ud;
\t\t\t\telse
\t\t\t\t\tshader = RendererOutputShader::s_fsr_easu_shader;
\t\t\t}
\t\t\tfilter = LatteTextureView::MagFilter::kLinear;
\t\t}
\t\telse if (scaling_filter == kNearestNeighborFilter)
\t\t{
\t\t\tif (renderUpsideDown)
\t\t\t\tshader = RendererOutputShader::s_copy_shader_ud;
\t\t\telse
\t\t\t\tshader = RendererOutputShader::s_copy_shader;''',
    'FSR output selection',
)

subprocess.run([
    'git', 'diff', '--check', '--',
    'src/config/CemuConfig.h',
    'src/gui/wxgui/GeneralSettings2.cpp',
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.h',
    'src/Cafe/HW/Latte/Renderer/RendererOuputShader.cpp',
    'src/Cafe/HW/Latte/Core/LatteRenderTarget.cpp',
], check=True)

print('[fsr-experiment] Added FidelityFX FSR 1 EASU upscale filter')
print('[fsr-experiment] UI: Graphics -> Upscale filter -> FidelityFX FSR (EASU)')
print('[fsr-experiment] Existing filter values/defaults are unchanged')
