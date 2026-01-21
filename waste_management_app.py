import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

# Konfigurasi Halaman
st.set_page_config(page_title="Dashboard Analisis Biaya Sampah", layout="wide")

# Judul Dashboard
st.title("📊 Dashboard Analisis Pengeluaran Sampah (Internal & Eksternal)")
st.markdown("Analisis fokus pada periode **Oktober - Desember 2025** sesuai permintaan.")

# --- FUNGSI LOAD DATA ---
@st.cache_data
def load_data():
    # 1. Load Data Internal
    df_internal = pd.read_excel("Waste Management/Data Sampah (frm bu Nina).xlsx", sheet_name="Internal (Giono)")
    
    # --- BERSIHKAN NAMA KOLOM ---
    df_internal.columns = df_internal.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    
    # Konversi kolom tanggal
    df_internal['Tgl kegiatan'] = pd.to_datetime(df_internal['Tgl kegiatan'], errors='coerce')
    
    # Daftar kolom biaya yang ingin dijumlahkan
    cols_biaya = [
        'Nominal Parkir', 
        'Nominal Tol', 
        'Nominal Tambal ban / Tambah angin', 
        'Biaya Retribusi Masuk TPS'
    ]
    
    # Bersihkan data numerik
    for col in cols_biaya:
        if col in df_internal.columns:
            if df_internal[col].dtype == 'object':
                 df_internal[col] = df_internal[col].astype(str).str.replace(',', '').str.replace('.', '', regex=False)
            df_internal[col] = pd.to_numeric(df_internal[col], errors='coerce').fillna(0)
    
    # Hitung Total Internal
    valid_cols = [c for c in cols_biaya if c in df_internal.columns]
    df_internal['Total_Internal'] = df_internal[valid_cols].sum(axis=1)

    # 2. Load Data Eksternal (Pembayaran/Keuangan)
    df_ext_finance = pd.read_excel("Waste Management/Data Sampah (frm bu Nina).xlsx", sheet_name="Sheet3")
    df_ext_finance.columns = df_ext_finance.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    df_ext_finance['Tanggal'] = pd.to_datetime(df_ext_finance['Tanggal'], errors='coerce')
    
    if df_ext_finance['Jumlah'].dtype == 'object':
        df_ext_finance['Jumlah'] = df_ext_finance['Jumlah'].astype(str).str.replace(',', '').str.replace('.', '', regex=False)
    df_ext_finance['Jumlah'] = pd.to_numeric(df_ext_finance['Jumlah'], errors='coerce').fillna(0)

    # 3. Load Data Operasional Eksternal
    df_ext_ops = pd.read_excel("Waste Management/Data Sampah (frm bu Nina).xlsx", sheet_name="Eksternal (UD Borneo)", header=8)
    df_ext_ops = df_ext_ops.loc[:, ~df_ext_ops.columns.str.contains('^Unnamed')]
    df_ext_ops.columns = df_ext_ops.columns.str.replace(r'\s+', ' ', regex=True).str.strip()
    df_ext_ops['TANGGAL'] = pd.to_datetime(df_ext_ops['TANGGAL'], errors='coerce')
    
    return df_internal, df_ext_finance, df_ext_ops

try:
    df_internal, df_ext_finance, df_ext_ops = load_data()
except FileNotFoundError:
    st.error("File Excel tidak ditemukan. Pastikan file ada di folder yang benar.")
    st.stop()
except Exception as e:
    st.error(f"Terjadi kesalahan: {e}")
    st.stop()

# --- SIDEBAR FILTER ---
st.sidebar.header("Filter Data")
default_start = pd.to_datetime("2025-10-01")
default_end = pd.to_datetime("2025-12-31")

start_date = pd.to_datetime(st.sidebar.date_input("Mulai Tanggal", default_start))
end_date = pd.to_datetime(st.sidebar.date_input("Sampai Tanggal", default_end))

# --- FILTERING DATA ---
mask_internal = (df_internal['Tgl kegiatan'] >= start_date) & (df_internal['Tgl kegiatan'] <= end_date)
df_int_filtered = df_internal.loc[mask_internal]

mask_ext_fin = (df_ext_finance['Tanggal'] >= start_date) & (df_ext_finance['Tanggal'] <= end_date)
df_ext_fin_filtered = df_ext_finance.loc[mask_ext_fin]

mask_ext_ops = (df_ext_ops['TANGGAL'] >= start_date) & (df_ext_ops['TANGGAL'] <= end_date)
df_ext_ops_filtered = df_ext_ops.loc[mask_ext_ops]

# --- MAIN KPI METRICS ---
total_internal = df_int_filtered['Total_Internal'].sum()
total_external = df_ext_fin_filtered['Jumlah'].sum()
grand_total = total_internal + total_external

col1, col2, col3 = st.columns(3)
col1.metric("Total Pengeluaran Internal", f"Rp {total_internal:,.0f}")
col2.metric("Total Pengeluaran Eksternal", f"Rp {total_external:,.0f}")
col3.metric("Grand Total Pengeluaran", f"Rp {grand_total:,.0f}")

st.divider()

# --- ANALISIS GRAFIK ---
col_chart1, col_chart2 = st.columns(2)

# 1. Pie Chart Internal
with col_chart1:
    st.subheader("Komposisi Biaya Internal")
    target_cols = ['Nominal Parkir', 'Nominal Tol', 'Nominal Tambal ban / Tambah angin', 'Biaya Retribusi Masuk TPS']
    existing_cols = [col for col in target_cols if col in df_int_filtered.columns]
    
    if existing_cols:
        cost_sums = df_int_filtered[existing_cols].sum().reset_index()
        cost_sums.columns = ['Kategori', 'Jumlah']
        fig_pie = px.pie(cost_sums, values='Jumlah', names='Kategori', hole=0.4, 
                         color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.warning("Kolom biaya detail tidak ditemukan.")

# 2. Bar Chart Bulanan (DIPERBAIKI)
with col_chart2:
    st.subheader("Tren Pengeluaran Bulanan")
    
    # Gunakan 'MS' (Month Start) agar tanggal agregasi adalah tgl 1 (bukan 30/31)
    monthly_int = df_int_filtered.set_index('Tgl kegiatan').resample('MS')['Total_Internal'].sum().reset_index()
    monthly_int['Type'] = 'Internal'
    monthly_int.rename(columns={'Tgl kegiatan': 'Bulan', 'Total_Internal': 'Jumlah'}, inplace=True)
    
    monthly_ext = df_ext_fin_filtered.set_index('Tanggal').resample('MS')['Jumlah'].sum().reset_index()
    monthly_ext['Type'] = 'Eksternal'
    monthly_ext.rename(columns={'Tanggal': 'Bulan', 'Jumlah': 'Jumlah'}, inplace=True)
    
    monthly_combined = pd.concat([monthly_int, monthly_ext])

    # Format kolom 'Bulan' menjadi string "NamaBulan Tahun" (contoh: October 2025)
    # Ini membuat sumbu X menjadi Kategori (Teks), bukan Waktu Kontinu, sehingga labelnya pasti pas.
    monthly_combined['Bulan_Str'] = monthly_combined['Bulan'].dt.strftime('%B %Y') 
    
    # Urutkan berdasarkan waktu agar urutan bulan benar
    monthly_combined = monthly_combined.sort_values('Bulan')
    
    if not monthly_combined.empty:
        # Gunakan 'Bulan_Str' sebagai sumbu X
        fig_bar = px.bar(monthly_combined, x='Bulan_Str', y='Jumlah', color='Type', barmode='group',
                         text_auto='.2s', 
                         color_discrete_map={'Internal': '#3366CC', 'Eksternal': '#DC3912'},
                         labels={'Bulan_Str': 'Bulan', 'Jumlah': 'Total Biaya (Rp)'})
        
        # Atur layout agar label sumbu X tidak miring jika tidak perlu
        fig_bar.update_layout(xaxis_title="Bulan")
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Tidak ada data untuk periode ini.")

# --- TREN HARIAN (LINE CHART) ---
st.subheader("Tren Pengeluaran Harian")
daily_int = df_int_filtered.groupby('Tgl kegiatan')['Total_Internal'].sum().reset_index()
daily_ext = df_ext_fin_filtered.groupby('Tanggal')['Jumlah'].sum().reset_index()

fig_line = go.Figure()
if not daily_int.empty:
    fig_line.add_trace(go.Scatter(x=daily_int['Tgl kegiatan'], y=daily_int['Total_Internal'], 
                                  mode='lines+markers', name='Internal', line=dict(color='#3366CC')))
if not daily_ext.empty:
    fig_line.add_trace(go.Scatter(x=daily_ext['Tanggal'], y=daily_ext['Jumlah'], 
                                  mode='lines+markers', name='Eksternal', line=dict(color='#DC3912')))

fig_line.update_layout(xaxis_title="Tanggal", yaxis_title="Jumlah (Rp)", hovermode="x unified")
st.plotly_chart(fig_line, use_container_width=True)

# --- ANALISIS OPERASIONAL ---
st.subheader("Analisis Operasional Eksternal (UD Borneo)")
col_ops1, col_ops2 = st.columns([1, 2])
with col_ops1:
    total_rit = df_ext_ops_filtered.shape[0]
    st.metric("Total Ritase", f"{total_rit} Rit")
    if 'VOLUME' in df_ext_ops_filtered.columns:
        if df_ext_ops_filtered['VOLUME'].dtype == 'object':
             df_ext_ops_filtered['VOLUME'] = pd.to_numeric(df_ext_ops_filtered['VOLUME'].astype(str).str.replace(',', '.'), errors='coerce')
        st.metric("Total Volume Sampah", f"{df_ext_ops_filtered['VOLUME'].sum():,.0f} m³")

with col_ops2:
    if 'LOKASI' in df_ext_ops_filtered.columns:
        rit_by_loc = df_ext_ops_filtered['LOKASI'].value_counts().reset_index()
        rit_by_loc.columns = ['Lokasi', 'Jumlah Rit']
        fig_rit = px.bar(rit_by_loc, x='Jumlah Rit', y='Lokasi', orientation='h', title="Ritase per Lokasi")
        st.plotly_chart(fig_rit, use_container_width=True)

# --- DATA TABLE ---
with st.expander("Lihat Data Detail"):
    loc_col = 'Lokasi Depo' if 'Lokasi Depo' in df_int_filtered.columns else 'Lokasi'
    final_view_cols = ['Tgl kegiatan', 'Tujuan', 'Total_Internal']
    if loc_col in df_int_filtered.columns:
        final_view_cols.insert(2, loc_col)
    final_view_cols.extend(existing_cols)
    
    if not df_int_filtered.empty:
         st.dataframe(df_int_filtered[final_view_cols])
    else:
         st.write("Data tidak tersedia.")