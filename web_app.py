import sys

import streamlit as st
import json
import os
import traceback
from generator import TestDataGenerator

# 页面配置
st.set_page_config(
    page_title="智能测试数据生成器 - DeepSeek",
    page_icon="🧪",
    layout="wide"
)

st.title("🧪 智能测试数据生成器")
st.markdown("基于 DeepSeek API，根据接口定义自动生成测试数据（正向/边界/异常）")

# 侧边栏配置
with st.sidebar:
    st.header("⚙️ 配置")

    api_key = st.text_input(
        "DeepSeek API Key",
        type="password",
        help="在 platform.deepseek.com 获取。新用户有10元免费额度。"
    )

    model = st.selectbox(
        "模型",
        ["deepseek-chat", "deepseek-reasoner"],
        help="deepseek-chat: 速度快，成本低；deepseek-reasoner: 推理更强，稍慢"
    )

    temperature = st.slider("创意度 (temperature)", 0.0, 1.0, 0.7, 0.1)

    st.divider()

    st.markdown("### 📝 生成参数")
    scenarios = st.multiselect(
        "测试场景",
        ["positive", "boundary", "negative"],
        default=["positive", "boundary", "negative"],
        help="positive: 正常数据；boundary: 边界值；negative: 异常数据"
    )

    count = st.slider("每组场景生成数量", 1, 20, 5)

    export_format = st.selectbox(
        "导出格式",
        ["json", "csv", "pytest", "postman"],
        help="选择输出格式"
    )

    st.markdown("---")
    st.caption("💡 提示：API Key 仅在当前会话中使用，不会保存。")

# 主区域
tab1, tab2, tab3 = st.tabs(["📄 直接输入 Schema", "📂 上传 JSON 文件", "🔗 Swagger 文档"])

def generate_and_display(schema, api_key, model, temperature, scenarios, count, export_format):
    """生成并显示测试数据"""
    if not api_key:
        st.error("❌ 请先在侧边栏输入 DeepSeek API Key")
        return

    with st.spinner("DeepSeek 正在生成测试数据..."):
        try:
            generator = TestDataGenerator(
                api_key=api_key,
                model=model,
                temperature=temperature
            )
            test_data = generator.generate(schema, count, scenarios)

            if not test_data:
                st.warning("未生成任何数据，请检查输入或稍后重试")
                return

            st.success(f"✅ 成功生成 {len(test_data)} 组测试数据")

            # 显示预览
            st.subheader("📊 数据预览")
            for idx, item in enumerate(test_data[:5]):  # 只显示前5条
                with st.expander(f"{idx+1}. [{item['scenario']}] {item['description']}"):
                    st.json(item['data'])
            if len(test_data) > 5:
                st.info(f"还有 {len(test_data)-5} 组数据未显示，请下载查看全部")

            # 导出
            content = generator.export_formats(test_data, export_format)
            file_extension = "json" if export_format == "json" else export_format
            if export_format == "pytest":
                file_extension = "py"
            st.download_button(
                label=f"📥 下载 ({export_format.upper()})",
                data=content,
                file_name=f"test_data.{file_extension}",
                mime="text/plain",
                use_container_width=True
            )

        except Exception as e:
            st.error(f"❌ 生成失败: {str(e)}")
            with st.expander("技术详情（用于调试）"):
                st.code(traceback.format_exc())

# Tab 1: 直接输入
with tab1:
    schema_input = st.text_area(
        "粘贴 API Schema (JSON 格式)",
        height=300,
        placeholder='{\n  "endpoint": "/api/login",\n  "method": "POST",\n  "parameters": {\n    "username": {"type": "string", "required": true},\n    "password": {"type": "string", "required": true}\n  }\n}'
    )

    if st.button("🚀 生成测试数据", type="primary", use_container_width=True):
        if not schema_input.strip():
            st.error("❌ 请输入 API Schema")
        else:
            try:
                schema = json.loads(schema_input)
                generate_and_display(schema, api_key, model, temperature, scenarios, count, export_format)
            except json.JSONDecodeError:
                st.error("❌ 输入的 Schema 不是有效的 JSON 格式")

# Tab 2: 上传文件
with tab2:
    uploaded_file = st.file_uploader(
        "上传 JSON 文件（包含 API Schema）",
        type=["json"],
        help="文件内容应为符合 API 定义的 JSON 对象"
    )

    if uploaded_file is not None:
        try:
            schema = json.load(uploaded_file)
            st.success("✅ 文件加载成功")
            with st.expander("查看 Schema 内容"):
                st.json(schema)

            if st.button("🚀 从文件生成测试数据", type="primary", use_container_width=True):
                generate_and_display(schema, api_key, model, temperature, scenarios, count, export_format)
        except json.JSONDecodeError:
            st.error("❌ 上传的文件不是有效的 JSON 格式")

# Tab 3: Swagger 文档
with tab3:
    swagger_url = st.text_input(
        "Swagger 文档 URL",
        placeholder="https://petstore.swagger.io/v2/swagger.json",
        help="输入 Swagger JSON 文件的 URL"
    )

    if st.button("🚀 批量生成", type="primary", use_container_width=True):
        if not api_key:
            st.error("❌ 请先在侧边栏输入 DeepSeek API Key")
        elif not swagger_url:
            st.error("❌ 请输入 Swagger URL")
        else:
            with st.spinner("正在处理 Swagger 文档..."):
                try:
                    generator = TestDataGenerator(
                        api_key=api_key,
                        model=model,
                        temperature=temperature
                    )
                    results = generator.generate_for_swagger(swagger_url, count)

                    st.success(f"✅ 处理完成，共 {len(results)} 个接口")

                    # 显示结果
                    for api_name, data in list(results.items())[:5]:
                        with st.expander(api_name):
                            if isinstance(data, dict) and "error" in data:
                                st.error(f"错误: {data['error']}")
                            else:
                                st.json(data)
                    if len(results) > 5:
                        st.info(f"还有 {len(results)-5} 个接口未显示")

                    # 批量导出为 zip
                    import zipfile
                    import io
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
                        for api_name, data in results.items():
                            filename = api_name.replace(' ', '_').replace('/', '_').replace('?', '') + ".json"
                            zip_file.writestr(filename, json.dumps(data, indent=2, ensure_ascii=False))
                    zip_buffer.seek(0)
                    st.download_button(
                        label="📦 下载全部 (ZIP)",
                        data=zip_buffer,
                        file_name="test_data_batch.zip",
                        mime="application/zip",
                        use_container_width=True
                    )

                except Exception as e:
                    st.error(f"❌ 处理失败: {str(e)}")
                    with st.expander("技术详情（用于调试）"):
                        st.code(traceback.format_exc())

# 页脚
st.markdown("---")
st.caption("💡 使用建议：先在小范围测试，确认生成效果后再批量使用。API 调用会产生费用，请合理控制生成次数。")