import streamlit as st
import pandas as pd
import altair as alt
from datetime import datetime, date, time, timedelta
import requests
import sqlite3
import os
import calendar

st.set_page_config(page_title="JadwalKu - Manajemen Waktu Harian", page_icon="🕐", layout="wide")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jadwalku.db")

CATEGORY_STYLE = {
    "Sholat": {"color": "#2e7d32", "icon": "🕌"},
    "Kuliah": {"color": "#1565c0", "icon": "📚"},
    "Istirahat": {"color": "#8e24aa", "icon": "🛋️"},
    "Makan": {"color": "#ef6c00", "icon": "🍽️"},
    "Tidur": {"color": "#37474f", "icon": "😴"},
    "Olahraga": {"color": "#c62828", "icon": "🏃"},
    "Belajar/Tugas": {"color": "#00838f", "icon": "💻"},
    "Lainnya": {"color": "#6d4c41", "icon": "📌"},
}

DEFAULT_SCHEDULE = [
    {"waktu_mulai": "04:30", "waktu_selesai": "05:00", "kegiatan": "Sholat Subuh", "kategori": "Sholat"},
    {"waktu_mulai": "05:00", "waktu_selesai": "06:00", "kegiatan": "Olahraga ringan", "kategori": "Olahraga"},
    {"waktu_mulai": "06:00", "waktu_selesai": "07:00", "kegiatan": "Mandi & bersiap", "kategori": "Lainnya"},
    {"waktu_mulai": "07:00", "waktu_selesai": "07:30", "kegiatan": "Sarapan", "kategori": "Makan"},
    {"waktu_mulai": "07:30", "waktu_selesai": "12:00", "kegiatan": "Kuliah", "kategori": "Kuliah"},
    {"waktu_mulai": "12:00", "waktu_selesai": "12:30", "kegiatan": "Sholat Dzuhur", "kategori": "Sholat"},
    {"waktu_mulai": "12:30", "waktu_selesai": "13:00", "kegiatan": "Makan siang", "kategori": "Makan"},
    {"waktu_mulai": "13:00", "waktu_selesai": "15:00", "kegiatan": "Kuliah / kerja tugas", "kategori": "Kuliah"},
    {"waktu_mulai": "15:00", "waktu_selesai": "15:30", "kegiatan": "Sholat Ashar", "kategori": "Sholat"},
    {"waktu_mulai": "15:30", "waktu_selesai": "17:00", "kegiatan": "Istirahat / santai", "kategori": "Istirahat"},
    {"waktu_mulai": "18:00", "waktu_selesai": "18:30", "kegiatan": "Sholat Maghrib", "kategori": "Sholat"},
    {"waktu_mulai": "18:30", "waktu_selesai": "19:15", "kegiatan": "Makan malam", "kategori": "Makan"},
    {"waktu_mulai": "19:15", "waktu_selesai": "19:45", "kegiatan": "Sholat Isya", "kategori": "Sholat"},
    {"waktu_mulai": "19:45", "waktu_selesai": "21:30", "kegiatan": "Belajar / kerjakan tugas", "kategori": "Belajar/Tugas"},
    {"waktu_mulai": "21:30", "waktu_selesai": "22:00", "kegiatan": "Waktu santai", "kategori": "Istirahat"},
    {"waktu_mulai": "22:00", "waktu_selesai": "04:30", "kegiatan": "Tidur", "kategori": "Tidur"},
]


def to_minutes(t_str):
    h, m = map(int, t_str.split(":"))
    return h * 60 + m


def fetch_prayer_times(city, country):
    try:
        url = "https://api.aladhan.com/v1/timingsByCity"
        params = {"city": city, "country": country, "method": 11}
        r = requests.get(url, params=params, timeout=8)
        r.json_data = r.json()
        if r.json_data.get("code") == 200:
            t = r.json_data["data"]["timings"]
            return {
                "Subuh": t["Fajr"],
                "Dzuhur": t["Dhuhr"],
                "Ashar": t["Asr"],
                "Maghrib": t["Maghrib"],
                "Isya": t["Isha"],
            }
    except Exception:
        return None
    return None


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS riwayat (
            tanggal TEXT,
            item_id INTEGER,
            waktu_mulai TEXT,
            waktu_selesai TEXT,
            kegiatan TEXT,
            kategori TEXT,
            selesai INTEGER,
            PRIMARY KEY (tanggal, item_id)
        )
    """)
    conn.commit()
    conn.close()


def save_progress(tanggal_str, jadwal_list):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM riwayat WHERE tanggal = ?", (tanggal_str,))
    conn.executemany(
        "INSERT INTO riwayat (tanggal, item_id, waktu_mulai, waktu_selesai, kegiatan, kategori, selesai) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (tanggal_str, j["id"], j["waktu_mulai"], j["waktu_selesai"], j["kegiatan"], j["kategori"], int(j["selesai"]))
            for j in jadwal_list
        ],
    )
    conn.commit()
    conn.close()


def load_progress(tanggal_str):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "SELECT item_id, waktu_mulai, waktu_selesai, kegiatan, kategori, selesai "
        "FROM riwayat WHERE tanggal = ? ORDER BY waktu_mulai",
        (tanggal_str,),
    )
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return None
    return [
        {"id": r[0], "waktu_mulai": r[1], "waktu_selesai": r[2], "kegiatan": r[3], "kategori": r[4], "selesai": bool(r[5])}
        for r in rows
    ]


def get_month_data(year, month):
    conn = sqlite3.connect(DB_PATH)
    pattern = f"{year:04d}-{month:02d}-%"
    df = pd.read_sql_query(
        "SELECT tanggal, item_id, waktu_mulai, waktu_selesai, kegiatan, kategori, selesai "
        "FROM riwayat WHERE tanggal LIKE ? ORDER BY tanggal, waktu_mulai",
        conn,
        params=(pattern,),
    )
    conn.close()
    return df


init_db()

if "jadwal" not in st.session_state:
    st.session_state.jadwal = [dict(item, selesai=False, id=i) for i, item in enumerate(DEFAULT_SCHEDULE)]
if "next_id" not in st.session_state:
    st.session_state.next_id = len(st.session_state.jadwal)

st.title("🕐 JadwalKu — Manajemen Waktu Harian")
st.caption("Atur kegiatanmu dari bangun tidur sampai tidur lagi: sholat, kuliah, makan, olahraga, istirahat, dan lainnya.")

with st.sidebar:
    st.header("⚙️ Pengaturan")
    tanggal = st.date_input("Tanggal", value=date.today())
    tanggal_str = tanggal.isoformat()

    if st.session_state.get("loaded_date") != tanggal_str:
        saved = load_progress(tanggal_str)
        if saved:
            st.session_state.jadwal = saved
            st.session_state.next_id = max(j["id"] for j in saved) + 1
        else:
            st.session_state.jadwal = [dict(item, selesai=False, id=i) for i, item in enumerate(DEFAULT_SCHEDULE)]
            st.session_state.next_id = len(st.session_state.jadwal)
        st.session_state.loaded_date = tanggal_str

    st.subheader("🕌 Waktu Sholat Otomatis")
    kota = st.text_input("Kota", "Jambi")
    negara = st.text_input("Negara", "Indonesia")
    if st.button("Ambil waktu sholat hari ini"):
        waktu = fetch_prayer_times(kota, negara)
        if waktu:
            st.success("Waktu sholat berhasil diambil, silakan sesuaikan jadwal sholat di bawah.")
            for nama, jam in waktu.items():
                st.write(f"**{nama}**: {jam}")
        else:
            st.error("Gagal mengambil waktu sholat. Cek koneksi internet atau isi jadwal sholat manual.")

    st.divider()
    st.subheader("➕ Tambah Kegiatan")
    with st.form("tambah_kegiatan", clear_on_submit=True):
        col1, col2 = st.columns(2)
        mulai = col1.time_input("Mulai", value=time(6, 0))
        selesai = col2.time_input("Selesai", value=time(7, 0))
        kegiatan = st.text_input("Nama kegiatan")
        kategori = st.selectbox("Kategori", list(CATEGORY_STYLE.keys()))
        submitted = st.form_submit_button("Tambahkan")
        if submitted and kegiatan.strip():
            st.session_state.jadwal.append({
                "waktu_mulai": mulai.strftime("%H:%M"),
                "waktu_selesai": selesai.strftime("%H:%M"),
                "kegiatan": kegiatan,
                "kategori": kategori,
                "selesai": False,
                "id": st.session_state.next_id,
            })
            st.session_state.next_id += 1
            st.rerun()

    st.divider()
    if st.button("🔄 Reset ke jadwal default"):
        st.session_state.jadwal = [dict(item, selesai=False, id=i) for i, item in enumerate(DEFAULT_SCHEDULE)]
        st.session_state.next_id = len(st.session_state.jadwal)
        st.rerun()

st.session_state.jadwal.sort(key=lambda x: to_minutes(x["waktu_mulai"]))

tab_harian, tab_bulanan = st.tabs(["📅 Jadwal Hari Ini", "📆 Riwayat Bulanan"])

with tab_harian:
    total = len(st.session_state.jadwal)
    selesai_count = sum(1 for j in st.session_state.jadwal if j["selesai"])
    progress = selesai_count / total if total else 0

    col_title, col_save = st.columns([3, 1])
    with col_title:
        st.subheader(f"📅 Jadwal — {tanggal.strftime('%A, %d %B %Y')}")
    with col_save:
        st.write("")
        if st.button("💾 Simpan Progress Hari Ini", use_container_width=True):
            save_progress(tanggal_str, st.session_state.jadwal)
            st.success("Progress hari ini tersimpan! Cek tab Riwayat Bulanan untuk melihat rekapnya.")

    st.progress(progress, text=f"Progress hari ini: {selesai_count}/{total} kegiatan selesai ({progress*100:.0f}%)")

    col_list, col_chart = st.columns([1.3, 1])

    with col_list:
        st.markdown("### ✅ To-Do List")
        for j in st.session_state.jadwal:
            style = CATEGORY_STYLE.get(j["kategori"], CATEGORY_STYLE["Lainnya"])
            c1, c2, c3 = st.columns([0.12, 0.7, 0.18])
            with c1:
                j["selesai"] = st.checkbox("", value=j["selesai"], key=f"chk_{j['id']}")
            with c2:
                label = f"{style['icon']} **{j['waktu_mulai']}–{j['waktu_selesai']}** — {j['kegiatan']} ({j['kategori']})"
                if j["selesai"]:
                    st.markdown(f"~~{label}~~")
                else:
                    st.markdown(label)
            with c3:
                if st.button("🗑️", key=f"del_{j['id']}"):
                    st.session_state.jadwal = [x for x in st.session_state.jadwal if x["id"] != j["id"]]
                    st.rerun()

    with col_chart:
        st.markdown("### 📊 Timeline Harian")
        rows = []
        for j in st.session_state.jadwal:
            start_m = to_minutes(j["waktu_mulai"])
            end_m = to_minutes(j["waktu_selesai"])
            if end_m <= start_m:
                end_m += 24 * 60
            rows.append({
                "Kegiatan": j["kegiatan"],
                "Kategori": j["kategori"],
                "start": start_m / 60,
                "end": end_m / 60,
            })
        color_scale = alt.Scale(
            domain=list(CATEGORY_STYLE.keys()),
            range=[v["color"] for v in CATEGORY_STYLE.values()],
        )
        if rows:
            df = pd.DataFrame(rows)
            chart = (
                alt.Chart(df)
                .mark_bar(height=14)
                .encode(
                    x=alt.X("start:Q", title="Jam", scale=alt.Scale(domain=[0, 28])),
                    x2="end:Q",
                    y=alt.Y("Kegiatan:N", sort=None, title=None),
                    color=alt.Color("Kategori:N", scale=color_scale, legend=alt.Legend(title="Kategori")),
                    tooltip=["Kegiatan", "Kategori", "start", "end"],
                )
                .properties(height=max(300, total * 28))
            )
            st.altair_chart(chart, use_container_width=True)

        st.markdown("### 📈 Ringkasan per Kategori")
        if rows:
            df["durasi_jam"] = df["end"] - df["start"]
            ringkasan = df.groupby("Kategori")["durasi_jam"].sum().reset_index()
            pie = (
                alt.Chart(ringkasan)
                .mark_arc(innerRadius=50)
                .encode(
                    theta="durasi_jam:Q",
                    color=alt.Color("Kategori:N", scale=color_scale),
                    tooltip=["Kategori", "durasi_jam"],
                )
            )
            st.altair_chart(pie, use_container_width=True)

    st.divider()
    csv_df = pd.DataFrame(st.session_state.jadwal)[["waktu_mulai", "waktu_selesai", "kegiatan", "kategori", "selesai"]]
    st.download_button(
        "⬇️ Download jadwal hari ini (CSV)",
        data=csv_df.to_csv(index=False).encode("utf-8"),
        file_name=f"jadwal_{tanggal.isoformat()}.csv",
        mime="text/csv",
    )

with tab_bulanan:
    st.subheader("📆 Rekap Bulanan")
    col_y, col_m = st.columns(2)
    with col_y:
        tahun_pilih = st.number_input("Tahun", min_value=2020, max_value=2100, value=tanggal.year, step=1)
    with col_m:
        bulan_pilih = st.selectbox(
            "Bulan",
            list(range(1, 13)),
            index=tanggal.month - 1,
            format_func=lambda m: calendar.month_name[m],
        )

    df_bulan = get_month_data(int(tahun_pilih), int(bulan_pilih))

    if df_bulan.empty:
        st.info("Belum ada progress yang disimpan untuk bulan ini. Simpan progress harian dulu di tab 'Jadwal Hari Ini'.")
    else:
        harian = df_bulan.groupby("tanggal").agg(
            total_kegiatan=("item_id", "count"),
            selesai=("selesai", "sum"),
        ).reset_index()
        harian["persen_selesai"] = (harian["selesai"] / harian["total_kegiatan"] * 100).round(1)

        st.markdown("### 📋 Daftar Hasil Harian")
        tampil = harian.rename(columns={
            "tanggal": "Tanggal",
            "total_kegiatan": "Total Kegiatan",
            "selesai": "Selesai",
            "persen_selesai": "Persen Selesai (%)",
        })
        st.dataframe(tampil, use_container_width=True, hide_index=True)

        rata_rata = harian["persen_selesai"].mean()
        total_hari_tercatat = len(harian)
        col_a, col_b = st.columns(2)
        col_a.metric("Rata-rata penyelesaian", f"{rata_rata:.0f}%")
        col_b.metric("Jumlah hari tercatat", f"{total_hari_tercatat} hari")

        st.markdown("### 📈 Grafik Penyelesaian per Hari")
        line_chart = (
            alt.Chart(harian)
            .mark_bar(color="#1565c0")
            .encode(
                x=alt.X("tanggal:N", title="Tanggal", sort=None),
                y=alt.Y("persen_selesai:Q", title="Persen Selesai (%)", scale=alt.Scale(domain=[0, 100])),
                tooltip=["tanggal", "total_kegiatan", "selesai", "persen_selesai"],
            )
        )
        st.altair_chart(line_chart, use_container_width=True)

        st.markdown("### 🗂️ Total Durasi per Kategori (Bulan Ini, Kegiatan Selesai)")
        df_selesai = df_bulan[df_bulan["selesai"] == 1].copy()
        if not df_selesai.empty:
            def durasi_jam(row):
                s = to_minutes(row["waktu_mulai"])
                e = to_minutes(row["waktu_selesai"])
                if e <= s:
                    e += 24 * 60
                return (e - s) / 60

            df_selesai["durasi_jam"] = df_selesai.apply(durasi_jam, axis=1)
            kategori_total = df_selesai.groupby("kategori")["durasi_jam"].sum().reset_index()
            kategori_color_scale = alt.Scale(
                domain=list(CATEGORY_STYLE.keys()),
                range=[v["color"] for v in CATEGORY_STYLE.values()],
            )
            pie_bulan = (
                alt.Chart(kategori_total)
                .mark_arc(innerRadius=50)
                .encode(
                    theta="durasi_jam:Q",
                    color=alt.Color("kategori:N", scale=kategori_color_scale, title="Kategori"),
                    tooltip=["kategori", "durasi_jam"],
                )
            )
            st.altair_chart(pie_bulan, use_container_width=True)
        else:
            st.caption("Belum ada kegiatan yang ditandai selesai bulan ini.")

        st.download_button(
            "⬇️ Download rekap bulanan (CSV)",
            data=tampil.to_csv(index=False).encode("utf-8"),
            file_name=f"rekap_{int(tahun_pilih)}_{int(bulan_pilih):02d}.csv",
            mime="text/csv",
        )