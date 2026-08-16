from pathlib import Path
import subprocess

ROOT = Path('.')


def replace_once(path_str: str, old_lf: str, new_lf: str) -> None:
    path = ROOT / path_str
    raw = path.read_bytes()
    text = raw.decode('utf-8')
    nl = '\r\n' if '\r\n' in text else '\n'
    old = old_lf.replace('\n', nl)
    new = new_lf.replace('\n', nl)
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f'{path_str}: anchor count={count}, expected 1')
    text = text.replace(old, new, 1)
    path.write_bytes(text.encode('utf-8'))


replace_once(
    'src/Cafe/HW/Latte/Core/LatteShader.h',
    '''\tstruct psImport_t
\t{
\t\tuint32 semanticId;
\t\tbool isFlat;
\t\tbool isNoPerspective;
\t};''',
    '''\tstruct psImport_t
\t{
\t\tuint32 semanticId;
\t\tuint8 defaultValue;
\t\tbool isFlat;
\t\tbool isNoPerspective;
\t};''',
)

replace_once(
    'src/Cafe/HW/Latte/Core/LatteShader.cpp',
    '''\t\tuint8 defaultValue = (psInputControl>>8)&3;
\t\t// default:
\t\t// 0 -> 0.0 0.0 0.0 0.0
\t\t// 1 -> 0.0 0.0 0.0 1.0
\t\t// 2 -> 1.0 1.0 1.0 0.0
\t\t// 3 -> 1.0 1.0 1.0 1.0
\t\tcemu_assert_debug(defaultValue <= 1);''',
    '''\t\tuint8 defaultValue = (psInputControl>>8)&3;
\t\t// default:
\t\t// 0 -> 0.0 0.0 0.0 0.0
\t\t// 1 -> 0.0 0.0 0.0 1.0
\t\t// 2 -> 1.0 1.0 1.0 0.0
\t\t// 3 -> 1.0 1.0 1.0 1.0
\t\tpsInputTable->import[f].defaultValue = defaultValue;''',
)

helpers = r'''
namespace LatteDecompiler
{
\tstatic bool _isPSInputWrittenByVS(LatteDecompilerShaderContext* shaderContext, sint32 psInputIndex)
\t{
\t\tLatteShaderPSInputTable* psInputTable = LatteSHRC_GetPSInputTable();
\t\tcemu_assert_debug(psInputIndex >= 0 && psInputIndex < psInputTable->count);

\t\tuint32 semanticId = psInputTable->import[psInputIndex].semanticId;
\t\tif (semanticId > LATTE_ANALYZER_IMPORT_INDEX_PARAM_MAX)
\t\t\treturn false;

\t\tuint32 parameterMask = shaderContext->shader->outputParameterMask;
\t\tfor (uint32 paramIndex = 0; paramIndex < 32; paramIndex++)
\t\t{
\t\t\tif ((parameterMask & (1u << paramIndex)) == 0)
\t\t\t\tcontinue;

\t\t\tuint32 vsSemanticId = LatteShaderPSInputTable::getVertexShaderOutParamSemanticId(shaderContext->contextRegisters, paramIndex);
\t\t\tif (psInputTable->getPSImportLocationBySemanticId(vsSemanticId) == psInputIndex)
\t\t\t\treturn true;
\t\t}

\t\treturn false;
\t}

\tstatic const char* _getPSInputDefaultValueGLSL(uint8 defaultValue)
\t{
\t\tswitch (defaultValue & 3)
\t\t{
\t\tcase 0:
\t\t\treturn "vec4(0.0, 0.0, 0.0, 0.0)";
\t\tcase 1:
\t\t\treturn "vec4(0.0, 0.0, 0.0, 1.0)";
\t\tcase 2:
\t\t\treturn "vec4(1.0, 1.0, 1.0, 0.0)";
\t\tcase 3:
\t\t\treturn "vec4(1.0, 1.0, 1.0, 1.0)";
\t\t}

\t\tcemu_assert_unimplemented();
\t\treturn "vec4(0.0)";
\t}

\tstatic void _emitPSInputDefaultsForVS(LatteDecompilerShaderContext* shaderContext)
\t{
\t\tLatteShaderPSInputTable* psInputTable = LatteSHRC_GetPSInputTable();
\t\tfor (sint32 i = 0; i < psInputTable->count; i++)
\t\t{
\t\t\tuint32 semanticId = psInputTable->import[i].semanticId;
\t\t\tif (semanticId > LATTE_ANALYZER_IMPORT_INDEX_PARAM_MAX)
\t\t\t\tcontinue;
\t\t\tif (_isPSInputWrittenByVS(shaderContext, i))
\t\t\t\tcontinue;

\t\t\tshaderContext->shaderSource->addFmt("passParameterSem{} = {};" _CRLF,
\t\t\t\tsemanticId, _getPSInputDefaultValueGLSL(psInputTable->import[i].defaultValue));
\t\t}
\t}
}
'''.strip('\n')

replace_once(
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSL.cpp',
    '''void _emitTypeConversionPrefix(LatteDecompilerShaderContext* shaderContext, sint32 sourceType, sint32 destinationType);
void _emitTypeConversionSuffix(LatteDecompilerShaderContext* shaderContext, sint32 sourceType, sint32 destinationType);
void LatteDecompiler_emitClauseCode(LatteDecompilerShaderContext* shaderContext, LatteDecompilerCFInstruction* cfInstruction, bool isSubroutine);

const char* _getShaderUniformBlockInterfaceName''',
    '''void _emitTypeConversionPrefix(LatteDecompilerShaderContext* shaderContext, sint32 sourceType, sint32 destinationType);
void _emitTypeConversionSuffix(LatteDecompilerShaderContext* shaderContext, sint32 sourceType, sint32 destinationType);
void LatteDecompiler_emitClauseCode(LatteDecompilerShaderContext* shaderContext, LatteDecompilerCFInstruction* cfInstruction, bool isSubroutine);

''' + helpers + '''

const char* _getShaderUniformBlockInterfaceName''',
)

replace_once(
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSLHeader.hpp',
    '''\t\t\tsrc->add("out");
\t\t\tsrc->addFmt(" vec4 passParameterSem{};" _CRLF, psInputTable->import[psInputIndex].semanticId);
\t\t}
\t}

\tvoid _emitPSImports''',
    '''\t\t\tsrc->add("out");
\t\t\tsrc->addFmt(" vec4 passParameterSem{};" _CRLF, psInputTable->import[psInputIndex].semanticId);
\t\t}

\t\t// Latte supplies SPI_PS_INPUT_CNTL.DEFAULT_VAL when a PS semantic has no
\t\t// active producer export. Vulkan still requires a matching stage interface.
\t\tsrc->add("#ifdef VULKAN" _CRLF);
\t\tfor (sint32 i = 0; i < psInputTable->count; i++)
\t\t{
\t\t\tif (psInputTable->import[i].semanticId > LATTE_ANALYZER_IMPORT_INDEX_PARAM_MAX)
\t\t\t\tcontinue;
\t\t\tif (_isPSInputWrittenByVS(shaderContext, i))
\t\t\t\tcontinue;

\t\t\tsrc->addFmt("layout(location = {}) ", i);
\t\t\tif (psInputTable->import[i].isFlat)
\t\t\t\tsrc->add("flat ");
\t\t\tif (psInputTable->import[i].isNoPerspective)
\t\t\t\tsrc->add("noperspective ");
\t\t\tsrc->add("out");
\t\t\tsrc->addFmt(" vec4 passParameterSem{};" _CRLF, psInputTable->import[i].semanticId);
\t\t}
\t\tsrc->add("#endif" _CRLF);
\t}

\tvoid _emitPSImports''',
)

replace_once(
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSL.cpp',
    '''\t\t}
\t}
\tfor(auto& cfInstruction : shaderContext->cfInstructions)
\t\tLatteDecompiler_emitClauseCode(shaderContext, &cfInstruction, false);''',
    '''\t\t}
\t}
\tif (shader->shaderType == LatteConst::ShaderType::Vertex && !shaderContext->options->usesGeometryShader)
\t{
\t\tsrc->add("#ifdef VULKAN" _CRLF);
\t\tLatteDecompiler::_emitPSInputDefaultsForVS(shaderContext);
\t\tsrc->add("#endif" _CRLF);
\t}
\tfor(auto& cfInstruction : shaderContext->cfInstructions)
\t\tLatteDecompiler_emitClauseCode(shaderContext, &cfInstruction, false);''',
)

subprocess.run([
    'git', 'diff', '--check', '--',
    'src/Cafe/HW/Latte/Core/LatteShader.h',
    'src/Cafe/HW/Latte/Core/LatteShader.cpp',
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSL.cpp',
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSLHeader.hpp',
], check=True)
subprocess.run([
    'git', 'diff', '--',
    'src/Cafe/HW/Latte/Core/LatteShader.h',
    'src/Cafe/HW/Latte/Core/LatteShader.cpp',
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSL.cpp',
    'src/Cafe/HW/Latte/LegacyShaderDecompiler/LatteDecompilerEmitGLSLHeader.hpp',
], check=True)
