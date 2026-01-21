import streamlit as st
import pandas as pd
import plotly.express as px

# --- CONFIG ---
st.set_page_config(page_title="Dashboard Waste Management", layout="wide")
FILE_PATH = 'Data Sampah.xlsx' 
HARGA_EKSTERNAL_PER_RIT = 350000

# --- DATA LOADER ---
@st.cache_data
def load_data():
    # 1. Internal
    df_int = pd.read_excel(FILE_PATH, sheet_name='Internal')
    df_int['Tgl kegiatan'] = pd.to_datetime(df_int['Tgl kegiatan'], errors='coerce')
    
    cols_biaya = {
        'Nominal\nParkir': 'Parkir', 'Nominal\nTol': 'Tol', 
        'Nominal\nTambal ban /\nTambah angin': 'Tambal Ban', 
        'Biaya Retribusi\nMasuk TPS': 'Retribusi', 'Debit': 'Debit'
    }
    df_int.rename(columns=cols_biaya, inplace=True)
    for col in cols_biaya.values():
        if col in df_int.columns:
            df_int[col] = pd.to_numeric(df_int[col], errors='coerce').fillna(0)
    
    df_int['Total_Biaya_Ops'] = df_int[list(cols_biaya.values())].sum(axis=1)
    df_int['Brt Bersih'] = pd.to_numeric(df_int['Brt Bersih'], errors='coerce').fillna(0)
    
    col_loc = [c for c in df_int.columns if 'Lokasi' in c][0]
    df_int['Lokasi_Clean'] = df_int[col_loc].astype(str).str.upper().str.strip()

    # 2. BBM & Maintenance
    df_bbm = pd.read_excel(FILE_PATH, sheet_name='Data BBM')
    df_bbm['Tanggal'] = pd.to_datetime(df_bbm['Tanggal'], errors='coerce')
    
    df_maint = pd.read_excel(FILE_PATH, sheet_name='Data Maintenance')
    df_maint['TANGGAL'] = pd.to_datetime(df_maint['TANGGAL'], errors='coerce')

    # 3. Eksternal
    try:
        df_raw = pd.read_excel(FILE_PATH, sheet_name='Eksternal', header=None)
        sheet_ext = 'Eksternal'
    except:
        df_raw = pd.read_excel(FILE_PATH, sheet_name='External', header=None)
        sheet_ext = 'External'
    
    header_idx = df_raw[df_raw.apply(lambda row: row.astype(str).str.contains('TANGGAL', case=False).any(), axis=1)].index[0]
    df_ext = pd.read_excel(FILE_PATH, sheet_name=sheet_ext, header=header_idx)
    df_ext['TANGGAL'] = pd.to_datetime(df_ext['TANGGAL'], errors='coerce')

    return df_int, df_bbm, df_maint, df_ext

# --- MAIN APP ---
try:
    df_int, df_bbm, df_maint, df_ext = load_data()
except Exception as e:
    st.error(f"Gagal membaca file: {e}")
    st.stop()

# --- HARDCODED FILTER DATE (OKT - NOV) ---
start_d = pd.to_datetime("2025-10-01")
end_d = pd.to_datetime("2025-11-30") 

df_int_f = df_int[(df_int['Tgl kegiatan'] >= start_d) & (df_int['Tgl kegiatan'] <= end_d)].copy()
df_ext_f = df_ext[(df_ext['TANGGAL'] >= start_d) & (df_ext['TANGGAL'] <= end_d)].copy()

# --- LOGIC PERHITUNGAN BIAYA ---
cutoff_date = pd.Timestamp('2025-12-27')

# 1. Filter Baris Valid Internal
mask_valid = ((df_int_f['Tgl kegiatan'] <= cutoff_date) & (df_int_f['BS'].notna()) & (df_int_f['VO'].notna())) | \
             (df_int_f['Tgl kegiatan'] > cutoff_date)
df_int_valid = df_int_f[mask_valid].copy()

# 2. Total Ops Dasar
list_komponen = ['Parkir', 'Tol', 'Tambal Ban', 'Retribusi', 'Debit']
breakdown_vals = df_int_valid[list_komponen].sum()
total_ops = breakdown_vals.sum()

# --- KOREKSI DATA 30 SEPTEMBER ---
cost_sept_30 = df_int[df_int['Tgl kegiatan'] == '2025-09-30']['Total_Biaya_Ops'].sum()
total_ops_corrected = total_ops - cost_sept_30

# 3. BBM & Maint
cost_bbm = df_bbm[(df_bbm['Tanggal'] >= start_d) & (df_bbm['Tanggal'] <= end_d)]['Total'].sum()
cost_maint = df_maint[df_maint['TANGGAL'].dt.month.isin([10, 11])]['JUMLAH_'].sum()

# Total Biaya Internal Final
total_int = total_ops_corrected + cost_bbm + cost_maint
weight_int = df_int_f['Brt Bersih'].sum()

# 4. Eksternal
total_ext = len(df_ext_f) * HARGA_EKSTERNAL_PER_RIT
weight_ext = df_ext_f['VOLUME'].sum() * 300

# --- VISUALISASI ---
st.title("📊 Dashboard Analisa Waste Management (Okt-Nov 2025)")

# KPI
c1, c2, c3, c4, c5, c6 = st.columns(6)
cost_per_kg_int = total_int/weight_int if weight_int else 0
cost_per_kg_ext = total_ext/weight_ext if weight_ext else 0

# Internal
c1.metric("Biaya Internal", f"Rp {total_int:,.0f}", help=f"Sudah dikurangi biaya 30 Sept (Rp {cost_sept_30:,.0f})")
c2.metric("Total Berat Internal", f"{weight_int:,.0f} Kg")
c3.metric("Cost/Kg Internal", f"Rp {cost_per_kg_int:,.0f}")

# Eksternal
c4.metric("Biaya Eksternal", f"Rp {total_ext:,.0f}")
c5.metric("Total Berat Eksternal", f"{weight_ext:,.0f} Kg", help="Asumsi Konversi: 1 m³ = 300 Kg")
c6.metric("Cost/Kg Eksternal", f"Rp {cost_per_kg_ext:,.0f}")

st.markdown("---")

# ROW 1
col_l, col_r = st.columns(2)

with col_l:
    st.subheader("Rincian Komponen Biaya Internal")
    df_bd = pd.DataFrame({
        'Komponen': list_komponen + ['BBM', 'Maintenance'],
        'Nilai': list(breakdown_vals.values) + [cost_bbm, cost_maint]
    })
    
    df_bd = df_bd[df_bd['Nilai'] > 0]
    
    fig_pie = px.pie(df_bd, values='Nilai', names='Komponen', hole=0.4)
    fig_pie.update_traces(textinfo='percent') 
    st.plotly_chart(fig_pie, use_container_width=True)

with col_r:
    st.subheader("Perbandingan Efisiensi (Biaya per Kg)")
    st.caption("Semakin rendah bar, semakin efisien/hemat.")
    
    df_comp = pd.DataFrame({
        'Vendor': ['Internal', 'Eksternal'],
        'Biaya per Kg (Rp)': [cost_per_kg_int, cost_per_kg_ext]
    })
    
    fig_bar = px.bar(df_comp, x='Vendor', y='Biaya per Kg (Rp)', color='Vendor', 
                     text_auto='.0f', color_discrete_map={'Internal':'#2ecc71', 'Eksternal':'#e74c3c'})
    st.plotly_chart(fig_bar, use_container_width=True)

st.markdown("---")

# TREN HARIAN
st.subheader("📈 Tren Pengeluaran Harian (Ops + BBM)")
df_int_daily = df_int_valid.groupby('Tgl kegiatan')['Total_Biaya_Ops'].sum().reset_index()
df_int_daily.rename(columns={'Tgl kegiatan': 'Tanggal'}, inplace=True)
df_bbm_daily = df_bbm[(df_bbm['Tanggal'] >= start_d) & (df_bbm['Tanggal'] <= end_d)].groupby('Tanggal')['Total'].sum().reset_index()
df_trend_int = pd.merge(df_int_daily, df_bbm_daily, on='Tanggal', how='outer').fillna(0)
df_trend_int['Biaya Internal'] = df_trend_int['Total_Biaya_Ops'] + df_trend_int['Total']

df_ext_daily = df_ext_f.groupby('TANGGAL').size().reset_index(name='Rit')
df_ext_daily['Biaya Eksternal'] = df_ext_daily['Rit'] * HARGA_EKSTERNAL_PER_RIT
df_ext_daily.rename(columns={'TANGGAL': 'Tanggal'}, inplace=True)

df_trend_final = pd.merge(df_trend_int[['Tanggal', 'Biaya Internal']], 
                          df_ext_daily[['Tanggal', 'Biaya Eksternal']], 
                          on='Tanggal', how='outer').fillna(0)

df_trend_melt = df_trend_final.melt(id_vars='Tanggal', value_vars=['Biaya Internal', 'Biaya Eksternal'], 
                                    var_name='Vendor', value_name='Biaya (Rp)')

fig_trend = px.line(df_trend_melt, x='Tanggal', y='Biaya (Rp)', color='Vendor', 
                    markers=True, 
                    color_discrete_map={'Biaya Internal':'#2ecc71', 'Biaya Eksternal':'#e74c3c'})
st.plotly_chart(fig_trend, use_container_width=True)

st.markdown("---")
st.subheader("🔍 Analisa Lanjutan")

# ROW 2
col_a1, col_a2 = st.columns(2)

with col_a1:
    # --- KAPASITAS TRUK DINAMIS ---
    MAX_CAPACITY = df_int_f['Brt Bersih'].max()
    if MAX_CAPACITY == 0: MAX_CAPACITY = 2500 
    
    st.markdown(f"**1. Utilitas Truk Internal (Load Factor)**")
    
    # --- KETERANGAN RANGE ---
    st.markdown(f"""
    <div style="font-size: 13px; color: white; margin-bottom: 10px;">
    <b>Keterangan Kategori (Benchmark Max: {MAX_CAPACITY:,.0f} Kg):</b><br>
    🔴 <b>Inefisien (<50%):</b> 0 - {MAX_CAPACITY*0.5:,.0f} Kg<br>
    🟠 <b>Kurang (50-75%):</b> {MAX_CAPACITY*0.5:,.0f} - {MAX_CAPACITY*0.75:,.0f} Kg<br>
    🟡 <b>Baik (75-90%):</b> {MAX_CAPACITY*0.75:,.0f} - {MAX_CAPACITY*0.9:,.0f} Kg<br>
    🟢 <b>Optimal (>90%):</b> > {MAX_CAPACITY*0.9:,.0f} Kg
    </div>
    """, unsafe_allow_html=True)
    
    labels_kategori = ['Inefisien (<50%)', 'Kurang (50-75%)', 'Baik (75-90%)', 'Optimal (>90%)']
    
    df_int_f['Load_Factor'] = (df_int_f['Brt Bersih'] / MAX_CAPACITY) * 100
    df_int_f['Kategori'] = pd.cut(df_int_f['Load_Factor'], bins=[-1, 50, 75, 90, 999], labels=labels_kategori)
    
    df_util_count = df_int_f['Kategori'].value_counts().reset_index()
    df_util_count.columns = ['Kategori', 'Jumlah Trip']
    
    color_map = {
        'Inefisien (<50%)': '#ef553b',  # Merah
        'Kurang (50-75%)': '#ffa15a',   # Oranye
        'Baik (75-90%)': '#fecb52',     # Kuning
        'Optimal (>90%)': '#00cc96'     # Hijau
    }
    
    fig_util = px.bar(df_util_count, x='Kategori', y='Jumlah Trip', color='Kategori', 
                      title="", 
                      color_discrete_map=color_map)
    st.plotly_chart(fig_util, use_container_width=True)
    
    st.markdown("###### Detail Data Trip (Hanya Data Ritase):")
    
    # FILTER TABEL: Hanya data yang memiliki berat sampah
    if 'Tonase Angkutan Sampah' in df_int_f.columns:
        mask_ritase = df_int_f['Tonase Angkutan Sampah'].notna()
    else:
        mask_ritase = df_int_f['Brt Bersih'] > 0
        
    df_show = df_int_f[mask_ritase].copy()
    
    cols_show = ['Tgl kegiatan', 'Lokasi_Clean', 'Brt Bersih', 'Load_Factor', 'Kategori']
    df_show = df_show[cols_show]
    
    # 1. SORTING NUMERIK (Load Factor terbesar di atas)
    df_show = df_show.sort_values(by='Load_Factor', ascending=False)
    
    # 2. FORMATTING TAMPILAN
    df_show['Tgl kegiatan'] = df_show['Tgl kegiatan'].dt.strftime('%Y-%m-%d')
    
    # Hapus baris pemformatan manual string ini agar tetap jadi angka untuk sorting!
    # df_show['Brt Bersih'] = df_show['Brt Bersih'].map('{:,.0f}'.format) 
    # df_show['Load_Factor'] = df_show['Load_Factor'].map('{:.1f}%'.format)
    
    # Gunakan column_config untuk mengatur tampilan angka
    st.dataframe(
        df_show, 
        use_container_width=True, 
        height=300,
        column_config={
            "Brt Bersih": st.column_config.NumberColumn(
                "Brt Bersih (Kg)",
                format="%d" # Tampilkan sebagai integer
            ),
            "Load_Factor": st.column_config.NumberColumn(
                "Load Factor",
                format="%.1f%%" # Tampilkan dengan %
            )
        }
    )

with col_a2:
    st.markdown("**2. Efisiensi Ritase Eksternal**")
    st.info("Optimal: Volume >= 4 m³. Boros: Volume < 4 m³.")
    df_ext_f['Status'] = df_ext_f['VOLUME'].apply(lambda x: 'Boros (<4m3)' if x < 4 else 'Optimal (>=4m3)')
    df_eff = df_ext_f['Status'].value_counts().reset_index()
    df_eff.columns = ['Status Efisiensi', 'Jumlah Rit']
    
    fig_eff = px.pie(df_eff, names='Status Efisiensi', values='Jumlah Rit', color='Status Efisiensi', 
                     color_discrete_map={'Boros (<4m3)':'red', 'Optimal (>=4m3)':'green'})
    st.plotly_chart(fig_eff, use_container_width=True)

# ROW 3
st.markdown("**3. Top 10 Sumber Sampah (Pareto Internal)**")
df_pareto = df_int_f.groupby('Lokasi_Clean')['Brt Bersih'].sum().sort_values(ascending=False).head(10).reset_index()
fig_par = px.bar(df_pareto, x='Brt Bersih', y='Lokasi_Clean', orientation='h', text_auto='.0f')
fig_par.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_par, use_container_width=True)