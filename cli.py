import click
import json
import traceback
from pathlib import Path
from generator import TestDataGenerator

@click.group()
def cli():
    """AI测试数据生成工具 - 基于 DeepSeek"""
    pass

@cli.command()
@click.option('--schema', '-s', required=True,
              help='API Schema文件路径或JSON字符串')
@click.option('--count', '-n', default=10,
              help='每个场景生成数据组数')
@click.option('--output', '-o', default='test_data.json',
              help='输出文件路径')
@click.option('--format', '-f', default='json',
              type=click.Choice(['json', 'csv', 'pytest', 'postman']),
              help='导出格式')
@click.option('--api-key', '-k',
              help='DeepSeek API Key (也可通过环境变量 DEEPSEEK_API_KEY 设置)')
@click.option('--model', '-m', default='deepseek-chat',
              help='模型名称 (deepseek-chat 或 deepseek-reasoner)')
@click.option('--temperature', '-t', default=0.7,
              help='生成温度 (0-1)')
@click.option('--scenarios',
              help='场景列表，逗号分隔 (如 positive,boundary,negative)')
def generate(schema, count, output, format, api_key, model, temperature, scenarios):
    """生成测试数据"""
    # 解析 schema
    try:
        if Path(schema).exists():
            with open(schema, 'r', encoding='utf-8') as f:
                api_schema = json.load(f)
        else:
            api_schema = json.loads(schema)
    except Exception as e:
        click.echo(f"❌ 无法解析 schema: {e}")
        return

    # 解析场景列表
    if scenarios:
        scenarios_list = [s.strip() for s in scenarios.split(',')]
    else:
        scenarios_list = None

    click.echo(f"🚀 正在使用 DeepSeek ({model}) 生成测试数据...")

    try:
        generator = TestDataGenerator(
            api_key=api_key,
            model=model,
            temperature=temperature
        )
        test_data = generator.generate(api_schema, count, scenarios_list)

        # 导出
        content = generator.export_formats(test_data, format)

        # 保存文件
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding='utf-8')

        click.echo(f"✅ 成功生成 {len(test_data)} 组数据，已保存至: {output}")

        # 打印预览
        click.echo("\n📊 预览 (前3条):")
        for item in test_data[:3]:
            click.echo(f"  [{item['scenario']}] {item['description']}")

    except Exception as e:
        click.echo(f"❌ 生成失败: {str(e)}")
        if click.confirm("是否显示详细错误信息？", default=False):
            click.echo(traceback.format_exc())

@cli.command()
@click.option('--swagger-url', '-u', required=True,
              help='Swagger 文档 URL')
@click.option('--output-dir', '-o', default='./test_data',
              help='输出目录')
@click.option('--api-key', '-k', help='DeepSeek API Key')
@click.option('--model', '-m', default='deepseek-chat', help='模型名称')
def batch(swagger_url, output_dir, api_key, model):
    """批量处理 Swagger 文档中的所有接口"""
    from pathlib import Path

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    click.echo(f"🚀 开始处理 Swagger 文档: {swagger_url}")

    generator = TestDataGenerator(api_key=api_key, model=model)
    try:
        results = generator.generate_for_swagger(swagger_url)

        for api_name, data in results.items():
            # 清理文件名
            filename = api_name.replace(' ', '_').replace('/', '_').replace('?', '')
            filepath = output_path / f"{filename}.json"

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            click.echo(f"✅ 已生成: {filename}")

        click.echo(f"\n🎉 完成！共处理 {len(results)} 个接口，数据保存在 {output_dir}")

    except Exception as e:
        click.echo(f"❌ 处理失败: {str(e)}")
        if click.confirm("是否显示详细错误信息？", default=False):
            click.echo(traceback.format_exc())

if __name__ == '__main__':
    cli()