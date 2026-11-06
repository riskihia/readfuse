# ReadFuse Translation Fidelity Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task in the current session, following the user's previously selected native execution method. Steps use checkbox (`- [ ]`) syntax for tracking. Implementation starts after this plan is approved.

**Goal:** Mengurangi penghilangan isi, perubahan makna, detail yang ditambahkan tanpa dasar, dan rujukan keliru; membedakan kelengkapan berkas dari pelaksanaan review semantik.

**Architecture:** Model agent tetap menerjemahkan dan menilai bahasa. Instruksi mengharuskan pembandingan setiap kalimat/klausa dengan sumber sebelum dan setelah penyuntingan. Helper Python hanya memvalidasi serta menyimpan bukti cakupan/versioning review; helper tidak menilai kebenaran bahasa melalui hash, regex, atau voting model.

**Tech Stack:** Python 3.10+, unittest, helper JSON/hash yang sudah ada. Tidak menambah layanan LLM, API key, atau dependency runtime wajib.

**Spec:** `docs/superpowers/specs/2026-11-06-readfuse-learning-edition-design.md`, terutama Content contract dan Success and failure criteria; temuan konkret dalam bagian Evidence di bawah memperjelas penerapannya.

**Status:** Proposed. Hanya dokumen rencana ini yang dibuat; kode skill dan terjemahan belum diperbaiki oleh tugas perencanaan ini.

## Global Constraints

- Translate all selected content, preserving meaning, nuance, authorial voice, qualifications, examples, argument relationships, and meaningful structure.
- Accessibility must not silently simplify away substantive content.
- Integrity checks and completion checks are distinct.
- Keep the existing local-first, agent-model workflow.
- Tambahan penjelasan harus tetap berlabel ReadFuse; jangan menyisipkan koreksi atau opini ke suara penulis.
- Pilihan bahasa boleh bervariasi. Jangan memaksakan satu padanan, penerjemahan kata demi kata, atau artikel Inggris sebagai aturan universal.
- Review mencakup seluruh cakupan terpilih, bukan seluruh buku secara otomatis. Konteks tetangga boleh dibaca untuk pemahaman tanpa ikut diterjemahkan.
- Pertahankan kompatibilitas job v2, valid work, pilihan bab/halaman, serta perilaku verify lama. Job tanpa laporan review berstatus belum ditinjau, bukan otomatis lulus.
- Bahan buku pengguna, terjemahan, dan review rinci tetap di `.readfuse-jobs/`; jangan menyalinnya ke fixture publik, commit, atau layanan eksternal.
- Tidak mengubah indeks/sumber hanya untuk menyembunyikan bagian yang belum diterjemahkan. Jika ekstraksi salah, catat masalah dan perbaiki melalui pekerjaan terpisah yang dapat ditelusuri.

## Evidence dan batas kesimpulan

Temuan yang dikonfirmasi pada hasil lokal Introduction, bukan sekadar preferensi reviewer:

| Segmen | Masalah | Kriteria perbaikan |
|---|---|---|
| `ch010-s00011` | Nuansa latent menjadi sekadar dimungkinkan | Pertahankan potensi yang terkandung tetapi belum muncul |
| `ch010-s00004` | Loose menjadi lentur; gerak sendiri kurang jelas | Pertahankan sifat dan tindakan yang dinyatakan sumber |
| `ch010-s00005` | Posisi partway down tidak terwakili | Posisi tidak hilang dan tidak ditetapkan sebagai titik tengah |
| `ch010-s00008` | Tambahan seolah pada kotak yang benar-benar ditopang | Jangan mengubah tindakan nyata menjadi kesan/perumpamaan |
| `ch010-s00020` | Penambahan begitu saja melemahkan penyangkalan | Jaga kekuatan klaim; konteks tambahan tetap di catatan |
| `ch010-s00021` | Is not menjadi bukan semata-mata | Pertahankan negasi tanpa pelunakan tak bersumber |
| `ch010-s00049` | Satu kalimat pembuka hilang saat mengubah rangkaian menjadi daftar | Pulihkan seluruh kalimat dan hubungan dengan segmen 50–54 |
| `ch010-s00059`, `ch010-s00063` | Elipsis berubah/hilang; satu penanda catatan kaki dibuat-buat | Cocokkan elipsis dan nomor rujukan dengan sumber sebenarnya |

Yang tidak dijadikan aturan tetap: A1/A2 mana yang selalu lebih natural; suppress wajib menekan; students wajib mahasiswa atau wajib murid; a selalu salah satu. Pilih berdasarkan makna dan konteks. Kesepakatan beberapa model tidak menjadi bukti sendiri.

## Review Focus

1. Satu kalimat dapat hilang walau ID dan hash valid: evaluasi semantik harus mendeteksi omission, bukan mengandalkan kelengkapan file (Tasks 1–2).
2. Satu kalimat sumber boleh menjadi beberapa kalimat target dan sebaliknya: pemeriksaan makna tidak boleh menuntut jumlah kalimat atau kata identik (Tasks 1–2).
3. Klaim kontroversial dapat mengundang pelunakan diam-diam: terjemahan mempertahankan klaim, catatan tidak mengatasnamakan penulis (Tasks 1–2, 5).
4. Review lama dapat di-record ulang setelah target berubah: snapshot input wajib cocok; laporan lama tidak boleh mengesahkan versi baru (Task 3).
5. Review satu bab tidak boleh ikut basi karena bab lain dilanjutkan: dependensi dan cakupan review dihitung per bab; perubahan pada bab yang sama membatalkan review terkait (Tasks 3–4).

## Pembagian file dan kontrak

- `SKILL.md`, `references/translation.md`, `references/quality.md`: alur penerjemahan dan pemeriksaan makna yang operasional.
- `references/explanations.md`, `references/summarization.md`: pemisahan suara penulis, klaim dan tambahan; periksa dampak revisi terjemahan pada keduanya.
- `references/architecture.md`, `README.md`, `assets/manifest.example.json`: dokumentasi review dan arti status yang sebenarnya.
- `tests/fixtures/translation-review-cases.json`: teks asli pendek buatan sendiri dan kandidat terjemahan, dengan kriteria makna; bukan kamus satu terjemahan benar.
- `scripts/readfuse/review.py`: validasi struktur laporan serta pengikatan input; tidak berisi penerjemah otomatis.
- `scripts/readfuse/state.py`: registrasi artifact `review`, dependensi dan status tambahan.
- `scripts/readfuse/cli.py`, `scripts/readfuse/assembly.py`, `scripts/readfuse/export.py`: akses CLI dan pelaporan status dalam hasil/metadata ekspor.
- `tests/test_review.py`, `tests/test_review_workflow.py`: pengujian metadata, perubahan versi, cakupan, dan kompatibilitas. Tes lama tetap dijalankan saat implementasi menyentuh kontraknya.
- `.readfuse-jobs/thinking-in-systems/`: revisi privat pendahuluan dan laporan perubahannya pada Task 5.

Kontrak laporan review yang diusulkan:

```json
{
  "version": 1,
  "chapter_id": "ch001",
  "coverage": ["ch001-s00001"],
  "source_sha256": "<original source hash>",
  "source_segments": {"ch001-s00001": "<source text hash>"},
  "inputs": {"heading:ch001": "<artifact hash>", "translation:ch001-s00001": "<artifact hash>", "notes:ch001-s00001": "<artifact hash>", "summary:ch001": "<artifact hash>"},
  "checks": ["completeness", "polarity_modality", "relations_details", "terminology", "references_structure", "fluency"],
  "verdict": "passed",
  "findings": [],
  "limitations": ["Agent review against extracted source; not an independent accuracy certification"]
}
```

`inputs` berisi tepat artifact konten yang diwajibkan mode/cakupan bab saat itu; mode translate tidak membutuhkan notes/summary, mode summarize tidak membutuhkan translation/notes. Review sendiri dikecualikan agar tidak membentuk dependensi melingkar. Jika style sheet atau glossary benar-benar dipakai sebagai input, simpan snapshot hash dalam field opsional `context_inputs` berisi path job-relative dan SHA-256; validasi ulang saat status. Jangan mengumpulkan snapshot konteks yang tidak dibaca.

`findings` berisi `segment_ids`, `category`, `explanation`, dan bukti singkat sumber/target yang relevan. Kategori: `omission`, `addition`, `meaning`, `detail`, `reference`, `source_uncertainty`, `style`. Laporan passed tidak boleh memiliki temuan substantif yang masih terbuka; perbedaan style yang diterima boleh dicatat. Laporan needs_revision harus mencantumkan masalah yang perlu ditangani. Bukti dan kelengkapan checklist merupakan catatan tindakan reviewer, bukan pembuktian otomatis bahwa hasilnya benar.

## Task 1: Perjelas aturan dan tahap pemeriksaan makna

**Files:** Modify `SKILL.md`, `references/translation.md`, `references/quality.md`, `references/explanations.md`, `references/summarization.md`.

**Interfaces:** Menghasilkan instruksi bagi host agent: pahami konteks → draf → bandingkan sumber per kalimat/klausa → rapikan bahasa → bandingkan ulang → notes/summary → review akhir bab. Tidak ada API LLM baru.

- [ ] Ubah panduan untuk memeriksa seluruh kalimat/klausa pada cakupan terpilih. Sumber dan target harus terlihat berdampingan; tandai hal hilang/bertambah/berubah. Penggabungan/pemisahan kalimat boleh jika semua makna tetap terwakili.
- [ ] Tambahkan pemeriksaan negasi, modalitas, kuantifier, atribusi, hubungan sebab-akibat, pelaku, sifat, arah, posisi dan urutan. Larang penambahan kepastian, pelunakan klaim, dan pembetulan klaim penulis secara diam-diam.
- [ ] Jelaskan penggunaan konteks: tetapkan tingkat pendidikan/sapaan hanya jika didukung sumber. Sifat benda tidak boleh diganti sifat lain demi kelancaran. Padanan dan ungkapan dinilai kontekstual, bukan di-hardcode dari satu contoh Slinky.
- [ ] Pisahkan error substantif dari pilihan gaya. Jaga metafora/idiom dan nada tanpa mewajibkan bentuk literal; pertahankan fungsi dan tingkat penekanannya.
- [ ] Perjelas rujukan: jangan menebak footnote dari elipsis; telusuri marker ke sumber ketika tersedia. Jika isi catatan belum dalam cakupan, pertahankan nomor dan nyatakan keterbatasannya.
- [ ] Batasi pemolesan: perubahan bentuk daftar/paragraf tidak boleh menghilangkan kalimat pengantar. Setelah revisi bahasa, cek ulang dengan sumber dan tinjau ulang notes; summary tetap berdasar sumber asli.
- [ ] Verifikasi instruksi melalui kasus Task 2, tanpa tes yang hanya mencari kata/heading dalam Markdown. Catat perbedaan perilaku yang dapat diamati.

## Task 2: Evaluasi perilaku dengan contoh asli yang dapat dipublikasikan

**Files:** Create `tests/fixtures/translation-review-cases.json`. Hasil evaluasi sementara disimpan di workspace terabaikan, bukan dalam fixture publik.

**Interfaces:** Fixture berisi `id`, `source`, `candidate`, `expected_findings` (kriteria makna, bukan satu kalimat terjemahan), dan `acceptable_variations`.

- [ ] Buat kasus pendek orisinal untuk kalimat terlewat, negasi yang dilunakkan, sifat benda tertukar, posisi sebagian dijadikan titik tengah, rujukan elipsis salah, serta gloss yang dimasukkan sebagai klaim penulis.
- [ ] Tambahkan kontrol valid: satu kalimat menjadi dua tanpa kehilangan makna; dua padanan alami sama-sama benar; pilihan jenjang yang dibuktikan konteks; artikel a yang tidak memerlukan padanan mekanis; catatan tambahan yang berlabel dan tidak mengubah suara penulis.
- [ ] Jalankan evaluasi agent dengan instruksi saat ini sebagai baseline sebelum Task 1 diterapkan, lalu instruksi revisi. Evaluator menerima sumber/kandidat/instruksi tanpa jawaban yang diharapkan; pengendali membandingkan temuan terhadap kriteria fixture setelahnya. Catat hasil sebenarnya, jangan mengarang kegagalan jika baseline sudah benar.
- [ ] Syarat lulus: evaluator menemukan seluruh omission/negation/reference error yang sengaja ditanam dan tidak menandai variasi yang setia sebagai salah hanya karena beda kata. Jika belum lulus, perbaiki instruksi berdasarkan kasus gagal, bukan menambah daftar kata terlarang universal.
- [ ] Jangan menyebut hasil evaluasi terbatas ini sebagai jaminan akurasi semua buku/bahasa. Tidak memerlukan langganan tiga model reviewer atau voting mereka.

## Task 3: Laporan review yang mengikuti versi konten

**Files:** Create `scripts/readfuse/review.py`, `tests/test_review.py`; modify `scripts/readfuse/state.py`.

**Interfaces:** `validate_review(payload: dict, state: dict, chapter_id: str) -> None`, `review_dependency(state: dict, chapter_id: str) -> dict`, `review_status(job: Path, state: dict, valid_artifact_keys: list[str]) -> dict`. Integrasikan melalui `record_artifact(job, {"kind":"review", "unit_id":chapter_id, "path":...})`; jangan membuat penyimpan state kedua.

- [ ] Tulis dan jalankan tes gagal `test_old_v2_job_has_no_semantic_review`, `test_pass_requires_exact_current_coverage_and_input_hashes`, `test_pass_rejects_open_meaning_findings`, `test_valid_style_variation_does_not_block_review`, `test_translation_change_stales_review`, `test_reregistering_old_report_does_not_bless_new_translation`, `test_notes_summary_heading_or_context_change_stales_review`, `test_same_chapter_extension_stales_review_but_other_chapter_extension_does_not`.
- [ ] Run: `python -m unittest discover -s tests -p test_review.py -v`. Expected: tes baru gagal karena perilaku review belum ada.
- [ ] Implementasikan schema di atas, record validation, hash snapshot exact, dan dependensi yang dihitung ulang. Payload lama tidak boleh otomatis diberi hash konten terbaru saat re-record. Pastikan seluruh prerequisite konten valid sebelum verdict passed diterima.
- [ ] Pakai safe paths, validasi kepemilikan artifact, atomic write dan lock existing. Tambahkan tes malformed report, path escape/alias, unsupported version, missing review file dan input artifact korup. Hindari circular import: fungsi review menerima snapshot state; state menangani IO/locking utama.
- [ ] Pertahankan `required_units` untuk artifact konten dan arti `requested_complete`/`book_complete`. Tambahkan `semantic_review` per bab (`not_reviewed`, `passed`, `needs_revision`, `stale`) dan `semantic_review_complete` (boolean, false bila selection kosong/konten belum lengkap/ada issue atau bab belum passed).
- [ ] Run: `python -m unittest discover -s tests -p test_review.py -v` dan `python -m unittest discover -s tests -p test_learning_state.py -v`. Expected: semua tes lulus; v2 lama masih terbaca tanpa review fiktif.

## Task 4: Integrasikan status dengan CLI, edisi dan dokumentasi

**Files:** Modify `scripts/readfuse/cli.py`, `scripts/readfuse/assembly.py`, `scripts/readfuse/export.py`, `references/architecture.md`, `README.md`, `assets/manifest.example.json`; create `tests/test_review_workflow.py`; extend `tests/test_assembly.py`/`tests/test_export.py` hanya untuk kontrak yang berubah.

**Interfaces:** `record --artifact` menerima kind review melalui API Task 3. `verify --require-reviewed` memerlukan artifact konten lengkap, integrity bersih, dan review passed/current pada seluruh cakupan terpilih; dapat dipakai sendiri tanpa harus mengulang flag require-complete. `status` dan `export-report.json` menampilkan status semantik secara terpisah.

- [ ] Tulis tes CLI sebelum implementasi: job lama lulus integrity tetapi gagal require-reviewed; artifact lengkap tanpa review tetap gagal require-reviewed; current passed review lulus; needs_revision/stale tidak lulus; reviewed partial selection boleh lulus tetapi tidak diklaim sebagai full book. Tambahkan alur revisi satu bab sambil mempertahankan bab lain.
- [ ] Run: `python -m unittest discover -s tests -p test_review_workflow.py -v`. Expected: tes flag/status baru gagal.
- [ ] Tambahkan flag/status tanpa mengubah arti verify lama. Assembly/export draf tetap diperbolehkan untuk pekerjaan yang belum ditinjau; beri keterangan pendek dan jujur tentang status review. Jangan menampilkan ID, hash, daftar error internal atau score semantik palsu dalam bacaan utama. Status passed berarti review agent tercatat, bukan sertifikasi akurasi.
- [ ] Dokumentasikan schema, flag, stale behavior, perbedaan integrity/coverage/review, dan contoh review fixture orisinal. Notes `reviewed:true` tidak boleh disalahartikan sebagai review semantik seluruh bab.
- [ ] Run: `python -m unittest discover -s tests -v`, CLI help yang berubah, dan `python C:/Users/LENOVO/.codex/skills/.system/skill-creator/scripts/quick_validate.py .`. Expected: suite dan validator lulus; optional-format/privileged skips dilaporkan eksplisit. Jangan install ulang dependency bila yang ada cukup.

## Task 5: Perbaiki pendahuluan Thinking in Systems dengan alur baru

**Files:** Hanya artifact yang perlu berubah di `.readfuse-jobs/thinking-in-systems/work/ch010/`, laporan review privat baru, checkpoint melalui API, dan `.readfuse-jobs/thinking-in-systems/edition/book.md` beserta format yang sebelumnya memang diminta pengguna.

**Interfaces:** Baca sumber yang tercatat pada `state/checkpoint.json`, bukan memilih salah satu dari dua folder inspeksi berdasarkan namanya. Gunakan record/review/assemble yang sudah diimplementasikan; jangan mengedit hash/state secara manual atau mengganti original source/index untuk perbaikan bahasa.

- [ ] Simpan salinan edisi saat ini dan artifact yang akan berubah ke backup privat dalam job; catat input hash. Pastikan sumber asli cocok. Jangan melakukan retranslation bab lain atau memperluas cakupan.
- [ ] Tinjau seluruh 63 segmen isi dan heading dengan sumber; jangan hanya memoles kutipan Slinky. Catat masalah dalam laporan perubahan privat. Prioritaskan kalimat hilang s00049, negasi s00020/s00021, footnote/elipsis s00059/s00063, lalu detail Slinky dan kelancaran.
- [ ] Revisi hanya bagian yang perlu. Jaga kesetiaan sumber walaupun klaimnya perlu konteks; tinjau catatan tambahan secara terpisah. Jangan menetapkan satu padanan wajib hanya karena reviewer menyukainya.
- [ ] Review ulang notes yang bergantung pada terjemahan berubah. Tinjau summary terhadap sumber; jika sudah akurat tidak perlu menulis ulang sekadar menambah variasi. Register kembali artifact berubah melalui API sebelum membuat snapshot review final.
- [ ] Buat laporan review yang mencakup seluruh cakupan intro, termasuk segmen tanpa perubahan. Passed hanya jika tidak ada temuan substantif terbuka; kalau ada ketidakpastian sumber, laporkan dan gunakan needs_revision.
- [ ] Jalankan `verify --require-reviewed --job-dir .readfuse-jobs/thinking-in-systems`, kemudian assemble/export format yang diminta. Baca hasil untuk memastikan kalimat dipulihkan, marker benar, catatan berlabel, judul tidak duplikat, dan tidak ada literal backslash-n atau karakter rusak. Bukti ini verifikasi hasil job, bukan pengujian ulang seluruh repo.
- [ ] Laporkan perubahan paling bermakna beserta tautan hasil dan keterbatasan review. Pertahankan edisi sebelumnya jika replacement gagal; tidak melakukan commit/push atau publikasi buku.

## Acceptance dan self-review

- Instruksi mengoperasionalkan semua temuan yang dikonfirmasi tanpa menjadikan contoh satu buku sebagai aturan leksikal universal (Tasks 1–2).
- Tes mekanis hanya menguji schema, snapshot dan stale behavior; evaluasi bahasa memakai kriteria makna independen terhadap sumber (Tasks 2–3).
- Status review melekat pada versi input yang benar dan tidak menyamakan checklist agent dengan pembuktian akurasi (Tasks 3–4).
- Alur lama dan job v2 tetap dapat dipakai; klaim kualitas baru bersifat eksplisit (Tasks 3–4).
- Hasil nyata yang memicu perbaikan direvisi, dapat dibandingkan dengan backup, dan tetap privat (Task 5).
- Kelima Review Focus memiliki pemeriksaan perilaku atau tes pada task pemiliknya. Tidak ada fitur OCR, parser baru, rewrite checkpoint total atau layanan reviewer berbayar dalam cakupan ini.

## Execution handoff

Tinjau rencana ini sebelum implementasi. Metode yang dipertahankan adalah pengerjaan langsung dalam sesi ini sesuai pilihan pengguna sebelumnya, dengan satu review independen pada hasil akhir bila tersedia/diizinkan. Urutan persiapan baseline Task 2 dilakukan sebelum revisi Task 1; kemudian selesaikan Task 1–2 sebagai satu siklus instruksi/evaluasi sebelum Task 3–5. Tidak ada perubahan kode, tes yang dijalankan, atau terjemahan yang diperbaiki selama tahap penyusunan rencana ini.
