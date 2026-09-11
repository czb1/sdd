"""
Main entry point for core-design skill.
Integrates new change creation, continue (step), and fast-forward (quick) modes.
"""

import sys
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

SCRIPTS_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPTS_DIR))

from cc_paths import setup_core_paths

# Use skill_bootstrap for path setup
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'core-shared' / 'scripts'))
from skill_bootstrap import skill_bootstrap
skill_bootstrap()

from core_new import create_change
from core_status import get_status, print_status
from core_instructions import get_instructions
from core_schema import list_schemas
from core_create_artifact import create_artifact_file
from core_change_context import load_change_context


def run_design_doc_reviewer(change_name: str, project_root: str, verbose: bool = False) -> Dict[str, Any]:
    """Run design-doc-reviewer after artifact generation."""
    reviewer_path = Path(project_root) / "coreharness-spec" / "skills" / "design-doc-reviewer" / "scripts" / "review.py"
    if not reviewer_path.exists():
        reviewer_path = Path(__file__).parent.parent.parent / "design-doc-reviewer" / "scripts" / "review.py"

    cmd = [sys.executable, str(reviewer_path), "--change", change_name, "--json"]
    if verbose:
        cmd.append("--verbose")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding="utf-8")
        if result.stdout:
            import json
            return json.loads(result.stdout)
    except Exception as e:
        print(f"Warning: Failed to run design-doc-reviewer: {e}")
    return None


def fast_forward_artifacts(change_name: str, project_root: str, schema: Optional[str] = None, design_rules_json: Optional[str] = None) -> Dict[str, Any]:
    """Fast-forward: create all remaining artifacts at once."""
    context = load_change_context(project_root, change_name, schema, design_rules_json)
    created = []
    
    for artifact_id in context.graph.get_next_artifacts(context.completed):
        try:
            instructions = get_instructions(change_name, artifact_id, project_root, schema)
            create_artifact_file(change_name, artifact_id, instructions.get('template', ''), project_root, schema, True, design_rules_json)
            created.append(artifact_id)
            context.completed.add(artifact_id)
        except Exception as e:
            print(f"Warning: Failed to create {artifact_id}: {e}")
    
    return {
        'change_name': change_name,
        'artifacts': created,
        'total': len(context.graph.get_all_artifacts()),
    }


def main():
    """Main entry point for core-design skill execution."""
    import argparse
    import json
    parser = argparse.ArgumentParser(description='CoreSpec Design Skill - supports step and quick modes')
    parser.add_argument('command', choices=['new', 'continue', 'cont', 'ff', 'fast', 'status', 'instructions', 'list-schemas'],
                        help='Command to execute')
    parser.add_argument('--name', help='Change name')
    parser.add_argument('--change', help='Change name (alias for --name)')
    parser.add_argument('--artifact', help='Artifact ID for instructions')
    parser.add_argument('--schema', help='Schema name')
    parser.add_argument('--project-root', default=os.getcwd(), help='Project root directory')
    parser.add_argument('--json', action='store_true', help='JSON output')
    parser.add_argument('--description', help='Change description')
    parser.add_argument('--step', action='store_true', help='Step mode: create one artifact at a time')
    parser.add_argument('--quick', action='store_true', help='Quick mode: create all artifacts at once')
    parser.add_argument('--no-review', action='store_true', help='Skip design-doc-reviewer after generation')
    parser.add_argument('--design-rules', help='path to json for rules')

    args = parser.parse_args()

    # args.design_rules = {"java": "### 封装性\n- 成员变量优先 `private`，通过方法暴露必要能力（getter/setter/受控修改）\n- 设置最小可访问性，减少外部依赖\n- 避免定义 `public` 且非 `final` 的类属性\n ### 简洁性\n- 方法应简短：非空非注释代码 ≤ 50 行，参数 ≤ 5 个，嵌套 ≤ 4 层\n- 使用卫语句（guard clause）提前返回/抛错，减少 if 嵌套\n- 每行声明一个变量，局部变量声明在接近首次使用的位置\n ### 防御式编程\n- 对外部输入、可空引用进行可靠校验\n- 使用 JSR 注解（`@NonNull/@Nullable`）明确 null 责任边界\n- 抛出新异常时保留原始异常信息作为 `cause`\n ### 契约式设计\n- 覆写方法必须加 `@Override`\n- 覆写 `equals` 必须同时覆写 `hashCode`\n- 使用 `@CheckReturnValue` 强调必须检查返回值的 API\n ## 异常处理规范（要求）\n\n- **G.ERR.01**：不要通过空的 catch 块忽略异常\n- **G.ERR.04**：防止通过异常泄露敏感信息\n- **G.ERR.05**：异常应与方法抽象层次对应\n- **G.ERR.08**：finally 块应正常结束，不改变控制流\n\n**异常处理原则**：\n- 可容错/可恢复使用受检异常；编程错误使用运行时异常\n- 能通过预检查避免的运行时异常，不用 try-catch 兜底\n- 业务失败优先用业务异常表达\n- 对外错误信息要通用、不暴露敏感细节\n ## 日志规范（要求）\n\n- **G.LOG.01**：使用 Facade 模式日志框架（slf4j+logback），禁止 `System.out/System.err`\n- **G.LOG.02**：Logger 实例必须声明为 `private static final` 或 `private final`\n- **G.LOG.03**：日志必须分等级（trace/debug/info/warning/error/fatal）\n- **G.LOG.05**：禁止直接使用外部数据记录日志（需校验和过滤）\n- **G.LOG.06**：禁止在日志中记录口令、密钥等敏感信息\n\n**日志使用**：\n- 生产环境不输出 trace/debug 日志\n- info 及以下级别使用占位符或条件判断避免不必要的字符串拼接\n- 敏感信息进行脱敏处理（密码替换为固定长度的 `*`）\n ## 并发与多线程\n\n- 优先使用高级并发抽象（Executor、Future、BlockingQueue、并发集合等）\n- 文档化类/方法的线程安全级别\n- 缩小锁范围，持锁只做快操作\n- 禁止使用废弃 API（Thread.suspend/resume/stop 等）\n ## 集合与泛型\n\n- 集合中优先使用泛型，避免原始类型与强制类型转换\n- `Collectors.toMap()` 注意相同 key 默认抛异常，value 为 `null` 会抛 NPE\n- `Arrays.asList()` 返回的 List 不支持 `add/remove`，与原数组共享存储\n- `List.subList()` 返回视图，与原 List 关联\n- `addAll(null)` 会抛 NPE\n"}

    if args.design_rules:
        with open(args.design_rules, 'r', encoding='utf-8') as f:
            design_rules = json.load(f)
            args.design_rules = design_rules

    change_name = args.name or args.change
    
    if args.command in ('new', 'continue', 'cont', 'ff', 'fast'):
        if not change_name:
            print("Error: --name or --change required")
            sys.exit(1)
    
    if args.command == 'new':
        try:
            result = create_change(change_name, args.project_root, args.schema, args.description)
            print(f"Created change: {result['name']}")
            print(f"Location: {result['change_dir']}")
            print(f"Schema: {result['schema']}")
            
            if args.quick:
                print("\nQuick mode: creating all artifacts...")
                ff_result = fast_forward_artifacts(change_name, args.project_root, args.schema, args.design_rules)
                print(f"Created {len(ff_result.get('artifacts', []))} artifacts")
                if not args.no_review:
                    print("\nRunning design-doc-reviewer...")
                    review_result = run_design_doc_reviewer(change_name, args.project_root, args.verbose)
                    if review_result:
                        status = review_result.get("overall_status", "UNKNOWN")
                        print(f"Design review: {status}")
                        if status == "FAIL":
                            print(f"Errors: {review_result.get('summary', '')}")
            else:
                print("\nReady for next artifact. Run with --step to continue.")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command in ('continue', 'cont'):
        try:
            if args.quick:
                result = fast_forward_artifacts(change_name, args.project_root, args.schema, args.design_rules)
                print(f"Fast-forward complete: {len(result.get('artifacts', []))} artifacts created")
                if not args.no_review:
                    print("\nRunning design-doc-reviewer...")
                    review_result = run_design_doc_reviewer(change_name, args.project_root, args.verbose)
                    if review_result:
                        status = review_result.get("overall_status", "UNKNOWN")
                        print(f"Design review: {status}")
                        if status == "FAIL":
                            print(f"Errors: {review_result.get('summary', '')}")
            else:
                context = load_change_context(args.project_root, change_name, args.schema, args.design_rules)
                next_artifacts = context.graph.get_next_artifacts(context.completed)
                if next_artifacts:
                    artifact_id = next_artifacts[0]
                    instructions = get_instructions(change_name, artifact_id, args.project_root, args.schema, args.design_rules)
                    result = create_artifact_file(change_name, artifact_id, instructions.get('template', ''), args.project_root, args.schema or 'spec-driven')
                    print(f"Created artifact: {artifact_id}")
                    print(f"Output: {result.get('output_path', 'N/A')}")
                    
                    next_after = context.graph.get_next_artifacts(context.completed | {artifact_id})
                    if next_after:
                        print(f"\nReady for next. Run with --step to continue.")
                    else:
                        print("\nAll artifacts created!")
                        if not args.no_review:
                            print("\nRunning design-doc-reviewer...")
                            review_result = run_design_doc_reviewer(change_name, args.project_root, args.verbose)
                            if review_result:
                                status = review_result.get("overall_status", "UNKNOWN")
                                print(f"Design review: {status}")
                                if status == "FAIL":
                                    print(f"Errors: {review_result.get('summary', '')}")
                else:
                    print("No more artifacts to create.")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command in ('ff', 'fast'):
        try:
            result = fast_forward_artifacts(change_name, args.project_root, args.schema, args.design_rules)
            print(f"Fast-forward complete: {len(result.get('artifacts', []))} artifacts created")
            for art in result.get('artifacts', []):
                print(f"  ✓ {art}")
            if not args.no_review:
                print("\nRunning design-doc-reviewer...")
                review_result = run_design_doc_reviewer(change_name, args.project_root, args.verbose)
                if review_result:
                    status = review_result.get("overall_status", "UNKNOWN")
                    print(f"Design review: {status}")
                    if status == "FAIL":
                        print(f"Errors: {review_result.get('summary', '')}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command == 'status':
        if not change_name:
            print("Error: --name or --change required for 'status' command")
            sys.exit(1)
        
        try:
            status = get_status(change_name, args.project_root, args.schema, args.json)
            if args.json:
                import json
                print(json.dumps(status, indent=2))
            else:
                print(print_status(status))
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command == 'instructions':
        if not change_name:
            print("Error: --name or --change required")
            sys.exit(1)
        if not args.artifact:
            print("Error: --artifact required")
            sys.exit(1)
        
        try:
            result = get_instructions(change_name, args.artifact, args.project_root, args.schema)
            if args.json:
                import json
                print(json.dumps(result, indent=2))
            else:
                print(f"Artifact: {result['artifactId']}")
                print(f"Description: {result['description']}")
                print(f"Output path: {result['outputPath']}")
                print(f"\nTemplate:\n{result['template']}")
                if result.get('dependencies'):
                    print(f"\nDependencies:")
                    for dep in result['dependencies']:
                        status = "done" if dep['done'] else "pending"
                        print(f"  - {dep['id']} ({status})")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)
    
    elif args.command == 'list-schemas':
        try:
            schemas = list_schemas(args.project_root)
            print("Available schemas:")
            for s in schemas:
                print(f"  - {s}")
        except Exception as e:
            print(f"Error: {e}")
            sys.exit(1)


if __name__ == '__main__':
    main()
