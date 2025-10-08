# python.py

import streamlit as st
import pandas as pd
from google import genai
from google.genai import types
from google.genai.errors import APIError

# --- Cấu hình Trang Streamlit ---
st.set_page_config(
    page_title="App Phân Tích Báo Cáo Tài Chính",
    layout="wide"
)

st.title("Ứng dụng Phân Tích Báo Cáo Tài Chính 📊")

# --- Hàm tính toán chính (Sử dụng Caching để Tối ưu hiệu suất) ---
@st.cache_data
def process_financial_data(df):
    """Thực hiện các phép tính Tăng trưởng và Tỷ trọng."""
    
    # Đảm bảo các giá trị là số để tính toán
    numeric_cols = ['Năm trước', 'Năm sau']
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
    
    # 1. Tính Tốc độ Tăng trưởng
    df['Tốc độ tăng trưởng (%)'] = (
        (df['Năm sau'] - df['Năm trước']) / df['Năm trước'].replace(0, 1e-9)
    ) * 100

    # 2. Tính Tỷ trọng theo Tổng Tài sản
    tong_tai_san_row = df[df['Chỉ tiêu'].str.contains('TỔNG CỘNG TÀI SẢN', case=False, na=False)]
    
    if tong_tai_san_row.empty:
        raise ValueError("Không tìm thấy chỉ tiêu 'TỔNG CỘNG TÀI SẢN'.")

    tong_tai_san_N_1 = tong_tai_san_row['Năm trước'].iloc[0]
    tong_tai_san_N = tong_tai_san_row['Năm sau'].iloc[0]

    # Xử lý chia cho 0
    divisor_N_1 = tong_tai_san_N_1 if tong_tai_san_N_1 != 0 else 1e-9
    divisor_N = tong_tai_san_N if tong_tai_san_N != 0 else 1e-9

    # Tính tỷ trọng
    df['Tỷ trọng Năm trước (%)'] = (df['Năm trước'] / divisor_N_1) * 100
    df['Tỷ trọng Năm sau (%)'] = (df['Năm sau'] / divisor_N) * 100
    
    return df

# --- Hàm gọi API Gemini cho Nhận xét Tự động (Chức năng 5) ---
def get_ai_analysis(data_for_ai, api_key):
    """Gửi dữ liệu phân tích đến Gemini API và nhận nhận xét."""
    try:
        client = genai.Client(api_key=api_key)
        model_name = 'gemini-2.5-flash' 

        prompt = f"""
        Bạn là một chuyên gia phân tích tài chính chuyên nghiệp. Dựa trên các chỉ số tài chính sau, hãy đưa ra một nhận xét khách quan, ngắn gọn (khoảng 3-4 đoạn) về tình hình tài chính của doanh nghiệp. Đánh giá tập trung vào tốc độ tăng trưởng, thay đổi cơ cấu tài sản và khả năng thanh toán hiện hành.
        
        Dữ liệu thô và chỉ số:
        {data_for_ai}
        """

        response = client.models.generate_content(
            model=model_name,
            contents=prompt
        )
        return response.text

    except APIError as e:
        return f"Lỗi gọi Gemini API: Vui lòng kiểm tra Khóa API hoặc giới hạn sử dụng. Chi tiết lỗi: {e}"
    except Exception as e:
        return f"Đã xảy ra lỗi không xác định: {e}"

# --- Hàm Xử lý Gửi Tin Nhắn Chatbot (Chức năng 6) ---
def handle_chat_input(prompt, api_key, df_context):
    """Gửi prompt người dùng kèm theo dữ liệu phân tích đến Gemini Chatbot."""
    
    # Khởi tạo hoặc khởi tạo lại dịch vụ chat khi dữ liệu mới được tải lên
    if "chat_service" not in st.session_state or df_context != st.session_state.get("current_df_context"):
        try:
            client = genai.Client(api_key=api_key)
            SYSTEM_PROMPT = (
                "Bạn là một trợ lý tài chính được cung cấp dữ liệu báo cáo tài chính đã phân tích. "
                "Hãy trả lời các câu hỏi dựa trên ngữ cảnh dữ liệu sau, và đưa ra thông tin phân tích chuyên sâu. "
                "Tuyệt đối không đưa ra thông tin nằm ngoài ngữ cảnh dữ liệu bạn được cung cấp. "
                f"\n\n--- DỮ LIỆU ĐÃ PHÂN TÍCH ---\n{df_context}"
            )
            chat = client.chats.create(
                model='gemini-2.5-flash',
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT)
            )
            st.session_state.chat_service = chat
            st.session_state.current_df_context = df_context
            st.session_state.chat_messages = [{"role": "model", "content": "Chào bạn! Tôi là Trợ lý phân tích tài chính AI. Dữ liệu của bạn đã được tải lên, bạn muốn hỏi gì về báo cáo này?"}]
        except Exception as e:
            st.error(f"Lỗi khởi tạo Chatbot: {e}")
            return
            
    # Thêm tin nhắn người dùng vào lịch sử hiển thị
    st.session_state.chat_messages.append({"role": "user", "content": prompt})
    
    # Gửi tin nhắn đến API
    try:
        with st.spinner("Gemini đang phân tích và trả lời..."):
            response = st.session_state.chat_service.send_message(prompt)
        
        # Thêm phản hồi của Gemini vào lịch sử hiển thị
        st.session_state.chat_messages.append({"role": "model", "content": response.text})
    except APIError as e:
        st.session_state.chat_messages.append({"role": "model", "content": f"Lỗi API: Không thể trả lời. Chi tiết: {e}"})
    
    # Kích hoạt Rerun để hiển thị tin nhắn mới
    st.rerun()


# --- Khởi tạo State (Lịch sử Chat) ---
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

# --- CHỨC NĂNG CHÍNH ---

# Chức năng 1: Tải File
uploaded_file = st.file_uploader(
    "1. Tải file Excel Báo cáo Tài chính (Chỉ tiêu | Năm trước | Năm sau)",
    type=['xlsx', 'xls']
)

df_processed = None 
api_key = st.secrets.get("GEMINI_API_KEY")

if uploaded_file is not None:
    if not api_key:
        st.error("Lỗi: Không tìm thấy Khóa API. Vui lòng cấu hình Khóa 'GEMINI_API_KEY' trong Streamlit Secrets.")
    else:
        try:
            df_raw = pd.read_excel(uploaded_file)
            
            # Tiền xử lý: Đảm bảo chỉ có 3 cột quan trọng
            df_raw.columns = ['Chỉ tiêu', 'Năm trước', 'Năm sau']
            
            # Xử lý dữ liệu
            df_processed = process_financial_data(df_raw.copy())

            if df_processed is not None:
                
                # --- Chức năng 2 & 3: Hiển thị Kết quả ---
                st.subheader("2. Tốc độ Tăng trưởng & 3. Tỷ trọng Cơ cấu Tài sản")
                st.dataframe(df_processed.style.format({
                    'Năm trước': '{:,.0f}',
                    'Năm sau': '{:,.0f}',
                    'Tốc độ tăng trưởng (%)': '{:.2f}%',
                    'Tỷ trọng Năm trước (%)': '{:.2f}%',
                    'Tỷ trọng Năm sau (%)': '{:.2f}%'
                }), use_container_width=True)
                
                # --- Chức năng 4: Tính Chỉ số Tài chính ---
                st.subheader("4. Các Chỉ số Tài chính Cơ bản")
                
                thanh_toan_hien_hanh_N = "N/A"
                thanh_toan_hien_hanh_N_1 = "N/A"
                
                try:
                    # Lấy Tài sản ngắn hạn
                    tsnh_n = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]
                    tsnh_n_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('TÀI SẢN NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                    # Lấy Nợ ngắn hạn
                    no_ngan_han_N = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm sau'].iloc[0]  
                    no_ngan_han_N_1 = df_processed[df_processed['Chỉ tiêu'].str.contains('NỢ NGẮN HẠN', case=False, na=False)]['Năm trước'].iloc[0]

                    # Tính toán (Xử lý chia cho 0)
                    thanh_toan_hien_hanh_N = tsnh_n / no_ngan_han_N if no_ngan_han_N != 0 else float('inf')
                    thanh_toan_hien_hanh_N_1 = tsnh_n_1 / no_ngan_han_N_1 if no_ngan_han_N_1 != 0 else float('inf')
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(
                            label="Chỉ số Thanh toán Hiện hành (Năm trước)",
                            value=f"{thanh_toan_hien_hanh_N_1:.2f} lần"
                        )
                    with col2:
                        st.metric(
                            label="Chỉ số Thanh toán Hiện hành (Năm sau)",
                            value=f"{thanh_toan_hien_hanh_N:.2f} lần",
                            delta=f"{thanh_toan_hien_hanh_N - thanh_toan_hien_hanh_N_1:.2f}"
                        )
                        
                except IndexError:
                    st.warning("Thiếu chỉ tiêu 'TÀI SẢN NGẮN HẠN' hoặc 'NỢ NGẮN HẠN' để tính chỉ số.")
                        
                # --- Chức năng 5: Nhận xét AI (Tự động) ---
                st.subheader("5. Nhận xét Tình hình Tài chính (AI)")
                
                # Chuẩn bị dữ liệu để gửi cho AI
                data_for_ai = pd.DataFrame({
                    'Chỉ tiêu': [
                        'Toàn bộ Bảng phân tích (dữ liệu thô)', 
                        'Thanh toán hiện hành (N-1)', 
                        'Thanh toán hiện hành (N)'
                    ],
                    'Giá trị': [
                        df_processed.to_markdown(index=False),
                        f"{thanh_toan_hien_hanh_N_1}", 
                        f"{thanh_toan_hien_hanh_N}"
                    ]
                }).to_markdown(index=False) 

                if st.button("Yêu cầu AI Phân tích"):
                    with st.spinner('Đang gửi dữ liệu và chờ Gemini phân tích...'):
                        ai_result = get_ai_analysis(data_for_ai, api_key)
                        st.markdown("**Kết quả Phân tích từ Gemini AI:**")
                        st.info(ai_result)

        except ValueError as ve:
            st.error(f"Lỗi cấu trúc dữ liệu: {ve}")
        except Exception as e:
            st.error(f"Có lỗi xảy ra khi đọc hoặc xử lý file: {e}. Vui lòng kiểm tra định dạng file.")

else:
    st.info("Vui lòng tải lên file Excel để bắt đầu phân tích.")

# ----------------------------------------------------------------------
# --- CHỨC NĂNG 6: CHATBOT HỎI ĐÁP CHUYÊN SÂU ---
# ----------------------------------------------------------------------

if uploaded_file is not None and df_processed is not None and api_key:
    st.markdown("---")
    st.subheader("6. Chatbot Hỏi đáp Chuyên sâu về Báo cáo 💬")
    
    # Chuẩn bị Context cho Chatbot
    chat_context = df_processed.to_markdown(index=False)
    
    # Hiển thị lịch sử chat
    for message in st.session_state.chat_messages:
        # st.chat_message(role) tự động chọn icon user/assistant
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # Khung nhập liệu chat (nằm dưới cùng màn hình)
    user_prompt = st.chat_input("Ví dụ: 'Giải thích tốc độ tăng trưởng của Tài sản ngắn hạn?'")

    if user_prompt:
        # Gọi hàm xử lý chat khi người dùng gửi tin nhắn
        handle_chat_input(user_prompt, api_key, chat_context)
