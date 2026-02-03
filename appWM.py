import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

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
    
    # Komponen yang DIHITUNG (Tanpa Debit)
    list_komponen_hitung = ['Parkir', 'Tol', 'Tambal Ban', 'Retribusi']
    
    # Cleaning numeric
    for col in cols_biaya.values():
        if col in df_int.columns:
            df_int[col] = pd.to_numeric(df_int[col], errors='coerce').fillna(0)
    
    # Hitung Total Hanya dari komponen hitung
    valid_cols_hitung = [c for c in list_komponen_hitung if c in df_int.columns]
    df_int['Total_Biaya_Ops'] = df_int[valid_cols_hitung].sum(axis=1)
    
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

# --- FILTER DATE (OKT - NOV 2025) ---
start_d = pd.to_datetime("2025-10-01")
end_d = pd.to_datetime("2025-11-30") 

df_int_f = df_int[(df_int['Tgl kegiatan'] >= start_d) & (df_int['Tgl kegiatan'] <= end_d)].copy()
df_ext_f = df_ext[(df_ext['TANGGAL'] >= start_d) & (df_ext['TANGGAL'] <= end_d)].copy()

# Helper: Hitung jumlah bulan (sekitar 2 bulan)
num_days = (end_d - start_d).days
num_months = max(1, round(num_days / 30)) 

# ==============================================================================
# LOGIKA PERHITUNGAN KHUSUS
# ==============================================================================

# 1. Perhitungan RITASE INTERNAL
if 'Tonase Angkutan Sampah' in df_int_f.columns:
    mask_ritase = df_int_f['Tonase Angkutan Sampah'].notna()
else:
    mask_ritase = df_int_f.index.notnull() 

df_rit_valid = df_int_f[mask_ritase]
count_rit_int = len(df_rit_valid)

# 2. Perhitungan BIAYA OPERASIONAL INTERNAL (KPI)
mask_biaya = df_int_f['BS'].notna() & df_int_f['VO'].notna()
df_biaya_valid = df_int_f[mask_biaya]

list_komponen = ['Parkir', 'Tol', 'Tambal Ban', 'Retribusi']
breakdown_vals = df_biaya_valid[list_komponen].sum() 
total_ops_valid = breakdown_vals.sum() 

# 3. BBM & Maintenance
cost_bbm = df_bbm[(df_bbm['Tanggal'] >= start_d) & (df_bbm['Tanggal'] <= end_d)]['Total'].sum()
cost_maint = df_maint[df_maint['TANGGAL'].dt.month.isin([10, 11])]['JUMLAH_'].sum()

# 4. Total Biaya Internal Final
total_int = total_ops_valid + cost_bbm + cost_maint

# 5. Total Berat Internal
weight_int = df_int_f['Brt Bersih'].sum() 

# --- LOGIC PERHITUNGAN BIAYA EKSTERNAL ---
count_rit_ext = len(df_ext_f) 
total_cost_ext = count_rit_ext * HARGA_EKSTERNAL_PER_RIT
weight_ext = df_ext_f['VOLUME'].sum() * 300
total_vol_ext_m3 = df_ext_f['VOLUME'].sum()

# --- DATA UNTUK SIMULASI (RATA-RATA) ---
if count_rit_int > 0:
    total_variable_cost_int = total_ops_valid + cost_bbm
    avg_cost_variable_per_rit = total_variable_cost_int / count_rit_int
else:
    avg_cost_variable_per_rit = 0
    total_variable_cost_int = 0

# --- VISUALISASI MONITORING ---
st.title("📊 Dashboard Analisa Waste Management (Okt-Nov 2025)")

# KPI
c1, c2, c3, c4, c5, c6 = st.columns(6)
cost_per_kg_int = total_int/weight_int if weight_int else 0
cost_per_kg_ext = total_cost_ext/weight_ext if weight_ext else 0

c1.metric("Biaya Internal (Total)", f"Rp {total_int:,.0f}", help="Hanya BS & VO Terisi. Periode Okt-Nov.")
c2.metric("Total Berat Internal", f"{weight_int:,.0f} Kg")
c3.metric("Cost/Kg Internal", f"Rp {cost_per_kg_int:,.0f}")
c4.metric("Biaya Eksternal (Total)", f"Rp {total_cost_ext:,.0f}")
c5.metric("Total Berat Eksternal", f"{weight_ext:,.0f} Kg")
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

# 1. Normalkan tanggal
df_int_f['Tanggal_Plot'] = df_int_f['Tgl kegiatan'].dt.normalize()
df_ext_f['Tanggal_Plot'] = df_ext_f['TANGGAL'].dt.normalize()

# 2. Filter Khusus Tren Harian
if 'Tonase Angkutan Sampah' in df_int_f.columns:
    df_trend_source = df_int_f[df_int_f['Tonase Angkutan Sampah'].notna()].copy()
else:
    df_trend_source = df_int_f.copy()

# 3. Grouping
df_int_daily = df_trend_source.groupby('Tanggal_Plot')['Total_Biaya_Ops'].sum().reset_index()
df_int_daily.rename(columns={'Tanggal_Plot': 'Tanggal'}, inplace=True)

df_bbm_daily = df_bbm[(df_bbm['Tanggal'] >= start_d) & (df_bbm['Tanggal'] <= end_d)].copy()
df_bbm_daily['Tanggal_Plot'] = df_bbm_daily['Tanggal'].dt.normalize()
df_bbm_daily_grp = df_bbm_daily.groupby('Tanggal_Plot')['Total'].sum().reset_index()
df_bbm_daily_grp.rename(columns={'Tanggal_Plot': 'Tanggal'}, inplace=True)

# Merge
df_trend_int = pd.merge(df_int_daily, df_bbm_daily_grp, on='Tanggal', how='outer').fillna(0)
df_trend_int['Biaya Internal'] = df_trend_int['Total_Biaya_Ops'] + df_trend_int['Total']

# External
df_ext_daily = df_ext_f.groupby('Tanggal_Plot').size().reset_index(name='Rit')
df_ext_daily['Biaya Eksternal'] = df_ext_daily['Rit'] * HARGA_EKSTERNAL_PER_RIT
df_ext_daily.rename(columns={'Tanggal_Plot': 'Tanggal'}, inplace=True)

# Final Merge
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
    MAX_CAPACITY = df_int_f['Brt Bersih'].max()
    if MAX_CAPACITY == 0: MAX_CAPACITY = 2500 
    
    st.markdown(f"**1. Utilitas Truk Internal (Load Factor)**")
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
    
    color_map = {'Inefisien (<50%)': '#ef553b', 'Kurang (50-75%)': '#ffa15a', 'Baik (75-90%)': '#fecb52', 'Optimal (>90%)': '#00cc96'}
    fig_util = px.bar(df_util_count, x='Kategori', y='Jumlah Trip', color='Kategori', title="", color_discrete_map=color_map)
    st.plotly_chart(fig_util, use_container_width=True)
    
    st.markdown("###### Detail Data Trip (Hanya Data Ritase):")
    if 'Tonase Angkutan Sampah' in df_int_f.columns:
        mask_ritase = df_int_f['Tonase Angkutan Sampah'].notna()
    else:
        mask_ritase = df_int_f['Brt Bersih'] > 0
    df_show = df_int_f[mask_ritase].copy()
    cols_show = ['Tgl kegiatan', 'Lokasi_Clean', 'Brt Bersih', 'Load_Factor', 'Kategori']
    df_show = df_show[cols_show]
    df_show = df_show.sort_values(by='Load_Factor', ascending=False)
    df_show['Tgl kegiatan'] = df_show['Tgl kegiatan'].dt.strftime('%Y-%m-%d')
    st.dataframe(df_show, use_container_width=True, height=300, 
                 column_config={
                     "Brt Bersih": st.column_config.NumberColumn("Brt Bersih (Kg)", format="%d"),
                     "Load_Factor": st.column_config.NumberColumn("Load Factor", format="%.1f%%")
                 })

with col_a2:
    st.markdown("**2. Efisiensi Ritase Eksternal**")
    st.info("Optimal: Volume >= 4 m³. Boros: Volume < 4 m³.")
    df_ext_f['Status'] = df_ext_f['VOLUME'].apply(lambda x: 'Boros (<4m3)' if x < 4 else 'Optimal (>=4m3)')
    df_eff = df_ext_f['Status'].value_counts().reset_index()
    df_eff.columns = ['Status Efisiensi', 'Jumlah Rit']
    fig_eff = px.pie(df_eff, names='Status Efisiensi', values='Jumlah Rit', color='Status Efisiensi', 
                     color_discrete_map={'Boros (<4m3)':'red', 'Optimal (>=4m3)':'green'})
    st.plotly_chart(fig_eff, use_container_width=True)

st.markdown("**3. Top 10 Sumber Sampah (Pareto Internal)**")
df_pareto = df_int_f.groupby('Lokasi_Clean')['Brt Bersih'].sum().sort_values(ascending=False).head(10).reset_index()
fig_par = px.bar(df_pareto, x='Brt Bersih', y='Lokasi_Clean', orientation='h', text_auto='.0f')
fig_par.update_layout(yaxis={'categoryorder':'total ascending'})
st.plotly_chart(fig_par, use_container_width=True)

# ==================================================================================================
# NEW SECTION: SIMULASI STRATEGI & INVESTASI
# ==================================================================================================
st.markdown("---")
st.header("🔧 Simulasi Strategi & Investasi")
st.caption(f"Menggunakan Data Rata-rata Bulanan dari Periode: {start_d.strftime('%d-%b')} s/d {end_d.strftime('%d-%b')} ({num_months} Bulan)")

# Common Help Texts
help_net_saving = "Uang yang dihemat karena jumlah ritase berkurang (tagihan vendor turun)"
help_net_profit = "Uang yang dihemat karena biaya angkut sendiri lebih murah dibandingkan bayar vendor"

tab1, tab2, tab3, tab4, tab5 = st.tabs(["1. Modifikasi Bak", "2. Peningkatan Ritase", "3. Tambah Armada", "4. Mesin Press Hydrolik", "5. Compactor Roller"])

# --- TAB 1: MODIFIKASI BAK ---
with tab1:
    st.subheader("Simulasi Peningkatan Kapasitas Bak")
    col1a, col1b = st.columns(2)
    with col1a:
        vol_current = 6.0 
        vol_target = st.number_input("Target Volume Baru (m3)", min_value=6.0, value=8.0, step=0.5)
        biaya_modif = st.number_input("Biaya Modifikasi Bak (Rp)", value=15000000, step=500000)
        
    with col1b:
        st.info("""
        ℹ️ **Aturan Dimensi Maksimal (PP No. 55 Tahun 2012):**
        1. **Tinggi Maksimal:** 4.200 mm (4,2 meter) dari permukaan tanah.
        2. **Lebar Maksimal:** 2.500 mm (2,5 meter).
        3. **Rasio Tinggi:** Tidak boleh lebih dari 1,7 kali lebar kendaraan.
        """)
    
    st.markdown("##### 🧮 Hasil Perhitungan Ekonomi:")
    if vol_target > vol_current:
        # Calculations
        pct_increase = (vol_target - vol_current) / vol_current
        
        avg_rit_ext_monthly = count_rit_ext / num_months
        
        # New Rit Calculation Logic
        ratio = vol_current / vol_target
        rit_baru_est = avg_rit_ext_monthly * ratio
        rit_hemat_monthly = avg_rit_ext_monthly - rit_baru_est
        
        uang_hemat_monthly = rit_hemat_monthly * HARGA_EKSTERNAL_PER_RIT
        uang_hemat_yearly = uang_hemat_monthly * 12
        
        bep_modif = biaya_modif / uang_hemat_monthly if uang_hemat_monthly > 0 else 0
        net_saving_y1 = uang_hemat_yearly - biaya_modif
        
        st.write(f"- Peningkatan Kapasitas: **{pct_increase*100:.1f}%**")
        st.write(f"- Potensi Pengurangan Ritase: **{rit_hemat_monthly:.1f} Rit/Bulan**")
        
        # --- DETAIL CALCULATION (FIXED FORMAT STRINGS) ---
        with st.expander("ℹ️ Detail Perhitungan Pengurangan Ritase"):
            st.markdown("**Konsep:** Volume bak yang lebih besar berarti truk bisa mengangkut lebih banyak sampah dalam satu kali jalan. Ini mengurangi frekuensi bolak-balik.")
            
            # Using .format() for safety
            st.latex(r"Rasio = \frac{{Vol_{{Awal}}}}{{Vol_{{Baru}}}} = \frac{{{:.1f}}}{{{:.1f}}} = {:.2f}".format(vol_current, vol_target, ratio))
            st.write(f"Artinya: 1 Rit truk baru setara dengan {(1/ratio):.2f} Rit truk lama.")
            
            st.markdown("**Perhitungan Ritase:**")
            st.latex(r"Rit_{{Avg}} = {:.1f} \text{{ Rit/Bulan}}".format(avg_rit_ext_monthly))
            st.latex(r"Rit_{{Baru}} = Rit_{{Avg}} \times Rasio = {:.1f} \times {:.2f} = {:.1f} \text{{ Rit}}".format(avg_rit_ext_monthly, ratio, rit_baru_est))
            st.latex(r"Hemat = Rit_{{Avg}} - Rit_{{Baru}} = {:.1f} - {:.1f} = \mathbf{{{:.1f}}} \text{{ Rit}}".format(avg_rit_ext_monthly, rit_baru_est, rit_hemat_monthly))
        # -----------------------------------------------
        
        c_res1, c_res2, c_res3 = st.columns(3)
        c_res1.metric("BEP (Balik Modal)", f"{bep_modif:.1f} Bulan")
        c_res2.metric("Net Saving per Bulan", f"Rp {uang_hemat_monthly:,.0f}", help=help_net_saving)
        c_res3.metric("Net Saving per Tahun", f"Rp {uang_hemat_yearly:,.0f}", help=help_net_saving)

# --- TAB 2: PENINGKATAN RITASE (LEMBUR) ---
with tab2:
    st.subheader("Analisa Marginal Cost (Lembur per Hari)")
    st.caption("Perhitungan upah lembur menggunakan standar Depnaker (1/173 x Gaji Sebulan).")
    
    c2a, c2b = st.columns(2)
    with c2a:
        target_rit_harian = st.number_input("Target Tambahan Rit per Hari", min_value=1, value=1)
        hari_kerja_lembur = st.number_input("Jumlah Hari Lembur per Bulan", min_value=1, max_value=31, value=25)
        
        st.markdown("###### ⏰ Kalkulator Upah Lembur:")
        gaji_total_karyawan = st.number_input("Total Gaji Bulanan", value=5000000, step=100000)
        jam_lembur = st.number_input("Estimasi Jam Lembur per Hari", min_value=1.0, value=2.0, step=0.5)
        
        # LOGIKA PERHITUNGAN LEMBUR
        upah_sejam = gaji_total_karyawan / 173
        jam_pertama = min(jam_lembur, 1.0)
        jam_berikutnya = max(0.0, jam_lembur - 1.0)
        
        biaya_lembur_jam1 = jam_pertama * 1.5 * upah_sejam
        biaya_lembur_next = jam_berikutnya * 2.0 * upah_sejam
        upah_lembur_harian = biaya_lembur_jam1 + biaya_lembur_next
        
        cost_lembur_per_rit = upah_lembur_harian / target_rit_harian
        marginal_cost_total = avg_cost_variable_per_rit + cost_lembur_per_rit
        vendor_price = HARGA_EKSTERNAL_PER_RIT
        net_profit_per_rit = vendor_price - marginal_cost_total
        
        # PROYEKSI BULANAN & TAHUNAN
        net_profit_monthly = net_profit_per_rit * target_rit_harian * hari_kerja_lembur
        net_profit_yearly = net_profit_monthly * 12
    
    with c2b:
        st.markdown("##### 🧮 Rincian Biaya:")
        st.markdown(f"""
        <div style="background-color: #262730; padding: 10px; border-radius: 5px; margin-bottom: 10px;">
        <b>Detail Perhitungan Lembur ({jam_lembur} Jam):</b><br>
        • Upah Sejam (1/173): Rp {upah_sejam:,.0f}<br>
        • Jam Pertama (1.5x): Rp {biaya_lembur_jam1:,.0f}<br>
        • Jam Berikutnya (2.0x): Rp {biaya_lembur_next:,.0f}<br>
        <b>Total Upah Lembur Hari Ini: Rp {upah_lembur_harian:,.0f}</b>
        </div>
        """, unsafe_allow_html=True)
        
        st.write(f"1. Biaya Variabel Internal: Rp {avg_cost_variable_per_rit:,.0f}/Rit")
        st.write(f"2. Alokasi Biaya Lembur: Rp {cost_lembur_per_rit:,.0f}/Rit")
        st.write(f"**Total Cost Internal: Rp {marginal_cost_total:,.0f}/Rit**")
        
        c_p1, c_p2, c_p3 = st.columns(3)
        c_p1.metric("Net Profit per Rit", f"Rp {net_profit_per_rit:,.0f}", help=help_net_profit)
        c_p2.metric("Net Profit per Bulan", f"Rp {net_profit_monthly:,.0f}", help=help_net_profit)
        c_p3.metric("Net Profit per Tahun", f"Rp {net_profit_yearly:,.0f}", help=help_net_profit)

# --- TAB 3: TAMBAH ARMADA ---
with tab3:
    st.subheader("Simulasi Beli Truk Baru")
    
    c3a, c3b = st.columns(2)
    with c3a:
        harga_truk = st.number_input("Harga Beli Truk (Rp)", value=350000000, step=10000000)
        gaji_supir_kernet = st.number_input("Total Gaji Bulanan (Rp/Bulan)", value=5000000)
        kapasitas_truk_baru = st.number_input("Kapasitas Truk Baru (m3)", value=6.0)
        
    with c3b:
        st.markdown("##### 🧮 Perhitungan Bulanan:")
        vol_ext_monthly = total_vol_ext_m3 / num_months
        rit_needed = vol_ext_monthly / kapasitas_truk_baru
        biaya_ops_baru = (rit_needed * avg_cost_variable_per_rit) + gaji_supir_kernet
        tagihan_vendor_avg = total_cost_ext / num_months
        
        saving_monthly = tagihan_vendor_avg - biaya_ops_baru
        saving_yearly = saving_monthly * 12
        
        st.write(f"- Tagihan Vendor Hilang: **Rp {tagihan_vendor_avg:,.0f}/Bulan**")
        st.write(f"- Biaya Operasional: **Rp {biaya_ops_baru:,.0f}/Bulan**")
        
        c_sav1, c_sav2, c_sav3 = st.columns(3)
        
        # LOGIKA VISUALISASI RUGI/LABA
        if saving_monthly > 0:
            bep_truk = harga_truk / saving_monthly
            c_sav1.metric("BEP (Balik Modal)", f"{bep_truk:.1f} Bulan")
        else:
            c_sav1.metric("BEP (Balik Modal)", "Tidak Balik Modal")
            
        c_sav2.metric("Net Saving per Bulan", f"Rp {saving_monthly:,.0f}", help=help_net_saving)
        c_sav3.metric("Net Saving per Tahun", f"Rp {saving_yearly:,.0f}", help=help_net_saving)

# --- TAB 4: HYDRAULIC PRESS ---
with tab4:
    st.subheader("Simulasi Mesin Press Hidrolik (Vertical Baler)")
    
    col4a, col4b = st.columns(2)
    
    with col4a:
        berat_bale = st.number_input("Estimasi Berat per Bale (Kg)", value=75, step=5, help="Berat hasil press dalam satu bale")
        
        harga_alat = st.number_input("Harga Mesin Press (Rp)", value=42000000, step=1000000)
        opex_alat = st.number_input("Biaya Listrik & Tali per Bulan (Rp)", value=600000, step=50000)
        
        batas_berat_truk = st.number_input("Batas Max Berat Truk (Kg)", value=2000)
    
    with col4b:
        st.markdown("##### 🧮 Detail Perhitungan:")
        densitas_loose = 300 
        kapasitas_vol_truk = 6.0 
        
        berat_simulasi = (weight_int / num_months) 
        
        # 1. Hitung Ritase LAMA (Loose)
        vol_loose_total = berat_simulasi / densitas_loose
        rit_lama_vol = vol_loose_total / kapasitas_vol_truk
        rit_lama_berat = berat_simulasi / batas_berat_truk
        rit_lama = max(rit_lama_vol, rit_lama_berat)
        
        # 2. Hitung Ritase BARU (Baled/Pressed)
        densitas_bale = 500 
        vol_per_bale = berat_bale / densitas_bale 
        
        bales_per_truck_vol = kapasitas_vol_truk / vol_per_bale
        bales_per_truck_weight = batas_berat_truk / berat_bale
        real_bales_per_trip = min(bales_per_truck_vol, bales_per_truck_weight)
        
        total_bales_needed = berat_simulasi / berat_bale
        rit_baru = total_bales_needed / real_bales_per_trip
        
        # --- DETAIL EXPANDER ---
        with st.expander("ℹ️ Detail Perhitungan & Asumsi"):
            st.markdown("**1. Kondisi Lama (Loose):**")
            st.write(f"- Densitas: **{densitas_loose} Kg/m³**")
            st.write(f"- Volume Sampah: {berat_simulasi:,.0f} / {densitas_loose} = **{vol_loose_total:.1f} m³**")
            st.write(f"- Ritase (Max Vol vs Berat): **{rit_lama:.1f} Rit**")

            st.markdown("**2. Kondisi Baru (Pressed Bale):**")
            st.write(f"- Berat per Bale: **{berat_bale} Kg**")
            st.write(f"- Estimasi Vol per Bale: {berat_bale}/{densitas_bale} = **{vol_per_bale:.2f} m³** (Asumsi densitas bale 500 kg/m³)")
            st.write(f"- Muatan Truk (by Vol): 6.0 / {vol_per_bale:.2f} = **{bales_per_truck_vol:.1f} Bale**")
            st.write(f"- Muatan Truk (by Berat): {batas_berat_truk} / {berat_bale} = **{bales_per_truck_weight:.1f} Bale**")
            st.write(f"- **Realita Angkut:** Maksimal **{int(real_bales_per_trip)} Bale/Trip** (Dibulatkan ke bawah)")
            st.latex(r"Rit_{{Baru}} = \frac{{TotalBale}}{{BalePerTrip}} = \frac{{{:.0f}}}{{{}}} = \mathbf{{{:.1f}}}".format(total_bales_needed, int(real_bales_per_trip), rit_baru))
        # -----------------------

        st.write(f"Ritase Tanpa Press: **{rit_lama:.1f} Rit**")
        st.write(f"Ritase Dengan Press: **{rit_baru:.1f} Rit**")
        
        delta_rit = rit_lama - rit_baru
        saving_rit_cost = delta_rit * avg_cost_variable_per_rit
        
        net_saving_alat_monthly = saving_rit_cost - opex_alat
        net_saving_alat_yearly = net_saving_alat_monthly * 12
        
        c_alat1, c_alat2, c_alat3 = st.columns(3)
        
        if net_saving_alat_monthly > 0:
            bep_alat = harga_alat / net_saving_alat_monthly
            c_alat1.metric("BEP (Balik Modal)", f"{bep_alat:.1f} Bulan")
        else:
            c_alat1.metric("BEP (Balik Modal)", "Tidak Balik Modal")
            
        c_alat2.metric("Net Saving per Bulan", f"Rp {net_saving_alat_monthly:,.0f}", help=help_net_saving)
        c_alat3.metric("Net Saving per Tahun", f"Rp {net_saving_alat_yearly:,.0f}", help=help_net_saving)

# --- TAB 5: COMPACTOR ROLLER ---
with tab5:
    st.subheader("Simulasi Alat Compactor (Roller)")
    
    col5a, col5b = st.columns(2)
    
    with col5a:
        pct_lunak = st.slider("Komposisi Sampah Lunak (%)", 0, 100, 70, key='pct_roller')
        rasio_padat = st.slider("Rasio Pemadatan (Kali Lipat)", 1.0, 4.0, 2.0, key='rasio_roller')
        
        opsi_roller = st.radio("Opsi Pengadaan Roller:", ["Beli (Investasi)", "Sewa (Bulanan)"], horizontal=True, key='opsi_roller')
        
        if opsi_roller == "Beli (Investasi)":
            harga_alat_rol = st.number_input("Harga Alat Compactor (Rp)", value=100000000, step=10000000, key='harga_roller')
            biaya_sewa_rol = 0
            opex_alat_rol = st.number_input("Biaya Operasional per Bulan", value=2000000, key='opex_roller')
        else:
            harga_alat_rol = 0
            biaya_sewa_rol = st.number_input("Biaya Sewa Roller per Bulan (Rp)", value=5000000, step=500000, key='sewa_roller')
            opex_alat_rol = 0 
            
        batas_berat_truk_rol = st.number_input("Batas Max Berat Truk (Kg)", value=2000, key='berat_roller')
    
    with col5b:
        st.markdown("##### 🧮 Detail Perhitungan:")
        densitas_loose = 300
        kapasitas_vol_truk = 6.0
        berat_simulasi = (weight_int / num_months)
        
        berat_lunak = berat_simulasi * (pct_lunak / 100)
        berat_keras = berat_simulasi * ((100-pct_lunak) / 100)
        
        vol_keras = berat_keras / densitas_loose
        vol_lunak_awal = berat_lunak / densitas_loose
        vol_lunak_akhir = vol_lunak_awal / rasio_padat
        total_vol_baru = vol_keras + vol_lunak_akhir
        
        rit_by_vol = total_vol_baru / kapasitas_vol_truk
        rit_by_weight = berat_simulasi / batas_berat_truk_rol
        
        rit_baru_rol = max(rit_by_vol, rit_by_weight)
        rit_lama_rol = max((berat_simulasi/densitas_loose)/kapasitas_vol_truk, berat_simulasi/batas_berat_truk_rol)
        
        # --- ADDED EXPANDER FOR ROLLER (FIXED FORMAT STRINGS) ---
        with st.expander("ℹ️ Detail Perhitungan & Asumsi"):
            st.markdown("**1. Asumsi Dasar:**")
            st.write(f"- Densitas Sampah Lepas (Loose): **{densitas_loose} Kg/m³**")
            st.write(f"- Kapasitas Volume Truk: **{kapasitas_vol_truk} m³**")

            st.markdown("**2. Pemisahan Sampah:**")
            st.latex(r"Berat_{{Lunak}} = {:,.0f} \times {}\% = {:,.0f} \text{{ Kg}}".format(berat_simulasi, pct_lunak, berat_lunak))
            st.latex(r"Berat_{{Keras}} = {:,.0f} \times {}\% = {:,.0f} \text{{ Kg}}".format(berat_simulasi, 100-pct_lunak, berat_keras))

            st.markdown("**3. Perubahan Volume (Compaction):**")
            st.write(f"Sampah lunak dipadatkan dengan rasio **{rasio_padat}x**.")
            st.latex(r"Vol_{{Keras}} = \frac{{{:.0f}}}{{{}}} = {:.2f} m^3".format(berat_keras, densitas_loose, vol_keras))
            st.latex(r"Vol_{{LunakAwal}} = \frac{{{:.0f}}}{{{}}} = {:.2f} m^3".format(berat_lunak, densitas_loose, vol_lunak_awal))
            st.latex(r"Vol_{{LunakAkhir}} = \frac{{{:.2f}}}{{{}}} = {:.2f} m^3".format(vol_lunak_awal, rasio_padat, vol_lunak_akhir))
            st.latex(r"TotalVol_{{Baru}} = {:.2f} + {:.2f} = {:.2f} m^3".format(vol_keras, vol_lunak_akhir, total_vol_baru))

            st.markdown("**4. Penentuan Ritase:**")
            st.markdown("**(A) Jika Dibatasi Volume (Bak Penuh):**")
            st.latex(r"Rit = \frac{{TotalVol_{{Baru}}}}{{KapasitasTruk}} = \frac{{{:.2f}}}{{{}}} = \mathbf{{{:.1f}}}".format(total_vol_baru, kapasitas_vol_truk, rit_by_vol))

            st.markdown("**(B) Jika Dibatasi Berat (Truk Keberatan):**")
            st.latex(r"Rit = \frac{{TotalBerat}}{{BatasMaxTruk}} = \frac{{{:.0f}}}{{{}}} = \mathbf{{{:.1f}}}".format(berat_simulasi, batas_berat_truk_rol, rit_by_weight))
        # ---------------------------------------------

        st.write(f"Ritase jika dibatasi Volume: **{rit_by_vol:.1f} Rit**")
        st.write(f"Ritase jika dibatasi Berat: **{rit_by_weight:.1f} Rit**")
        
        delta_rit_rol = rit_lama_rol - rit_baru_rol
        saving_rit_cost_rol = delta_rit_rol * avg_cost_variable_per_rit
        
        if opsi_roller == "Beli (Investasi)":
             net_saving_rol_monthly = saving_rit_cost_rol - opex_alat_rol
        else:
             net_saving_rol_monthly = saving_rit_cost_rol - biaya_sewa_rol
             
        net_saving_rol_yearly = net_saving_rol_monthly * 12
        
        c_rol1, c_rol2, c_rol3 = st.columns(3)
        
        if opsi_roller == "Beli (Investasi)":
            if net_saving_rol_monthly > 0:
                bep_rol = harga_alat_rol / net_saving_rol_monthly
                c_rol1.metric("BEP (Balik Modal)", f"{bep_rol:.1f} Bulan")
            else:
                c_rol1.metric("BEP (Balik Modal)", "Tidak Balik Modal")
        else:
            c_rol1.metric("Metode", "Sewa Bulanan")
            
        c_rol2.metric("Net Saving per Bulan", f"Rp {net_saving_rol_monthly:,.0f}", help=help_net_saving)
        c_rol3.metric("Net Saving per Tahun", f"Rp {net_saving_rol_yearly:,.0f}", help=help_net_saving)