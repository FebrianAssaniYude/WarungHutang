import os
import platform
import subprocess
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    HRFlowable,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Paragraph,
)

from utils.formatter import (
    BULAN_INDONESIA,
    format_rupiah,
    format_date_indonesia,
)
from utils.error_handler import log_error
from models.settings import SettingsModel


# =============================================================
# TOKEN PDF
# Semua ukuran, warna, dan jarak dokumen PDF ada di sini agar
# keenam dokumen memiliki tampilan yang sama. Dicetak hitam-putih,
# jadi hanya memakai hitam dan abu-abu.
# =============================================================

PAGE_MARGIN = 15 * mm
CONTENT_WIDTH = 180 * mm          # A4 (210 mm) - 2 x margin 15 mm

SECTION_GAP = 5 * mm              # jarak antar bagian dokumen
SMALL_GAP = 3 * mm

INFO_LABEL_WIDTH = 40 * mm
SUMMARY_WIDTH = 110 * mm
SUMMARY_LABEL_WIDTH = 70 * mm

CELL_PADDING = 5

# Lebar kolom (total selalu 180 mm = CONTENT_WIDTH)
ITEM_COLUMNS = [80 * mm, 18 * mm, 38 * mm, 44 * mm]
HISTORY_COLUMNS = [30 * mm, 22 * mm, 50 * mm, 36 * mm, 42 * mm]
REPORT_COLUMNS = [34 * mm, 72 * mm, 28 * mm, 46 * mm]
STAT_COLUMNS = [90 * mm, 90 * mm]

COLOR_TEXT = colors.black
COLOR_MUTED = colors.HexColor("#555555")
COLOR_GRID = colors.HexColor("#9CA3AF")
COLOR_HEADER_BG = colors.HexColor("#E5E5E5")
COLOR_ZEBRA = colors.HexColor("#F5F5F5")

FONT = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

SUPPORTED_DOCUMENTS = {
    "sale",
    "purchase",
    "debt",
    "payment",
    "customer_history",
    "monthly_report",
}


class PrinterError(Exception):
    """Error khusus untuk proses generate/print PDF."""


class Printer:
    """
    Engine printing reusable untuk aplikasi Warung Hutang.

    Tanggung jawab:
    - Membuat PDF transaksi, riwayat pelanggan, dan laporan bulanan.
    - Menyediakan PDF sementara untuk preview.
    - Menyimpan PDF secara permanen.
    - Membuka PDF menggunakan aplikasi PDF bawaan OS.

    Modul ini tidak bergantung pada UI CustomTkinter sehingga
    dapat digunakan oleh berbagai halaman aplikasi.
    """

    def __init__(self, store_name: Optional[str] = None):
        if store_name:
            self.store_name = store_name
        else:
            try:
                self.store_name = SettingsModel().get_nama_warung()
            except Exception:
                self.store_name = "Warung Hutang"

        self._printed_at = ""
        self._running_header = ""

    # =========================================================
    # PUBLIC API
    # =========================================================

    def create_pdf(
        self,
        document_type: str,
        data: Dict[str, Any],
        output_path: Optional[str] = None,
    ) -> str:
        """
        Membuat PDF berdasarkan jenis dokumen.

        document_type yang didukung:
        - sale
        - purchase
        - debt
        - payment
        - customer_history
        - monthly_report

        Returns:
            Path PDF yang berhasil dibuat.
        """
        document_type = (document_type or "").strip().lower()

        if document_type not in SUPPORTED_DOCUMENTS:
            raise PrinterError(
                f"Jenis dokumen tidak didukung: {document_type}"
            )

        if output_path is None:
            output_path = self.create_temp_pdf_path(
                prefix=f"warung_hutang_{document_type}_"
            )

        output_path = os.path.abspath(output_path)

        output_dir = os.path.dirname(output_path)

        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        try:
            self._printed_at = datetime.now().strftime("%d-%m-%Y %H:%M")
            self._running_header = ""

            doc = SimpleDocTemplate(
                output_path,
                pagesize=A4,
                rightMargin=PAGE_MARGIN,
                leftMargin=PAGE_MARGIN,
                topMargin=PAGE_MARGIN,
                bottomMargin=PAGE_MARGIN,
                title=self._get_document_title(document_type),
                author=self.store_name,
            )

            styles = self._build_styles()

            elements = self._build_document(
                document_type,
                data,
                styles,
            )

            doc.build(
                elements,
                onFirstPage=self._draw_footer,
                onLaterPages=self._draw_later_page,
            )

        except Exception as exc:
            error_text = (
                f"Printer.create_pdf gagal.\n"
                f"Jenis dokumen: {document_type}\n"
                f"Output: {output_path}\n"
                f"Error: {exc}"
            )

            log_error(error_text)

            raise PrinterError(
                "Gagal membuat PDF. Silakan coba lagi."
            ) from exc

        if not os.path.exists(output_path):
            raise PrinterError(
                "PDF tidak berhasil dibuat."
            )

        return output_path

    def create_temp_pdf_path(
        self,
        prefix: str = "warung_hutang_",
    ) -> str:
        """
        Membuat path file PDF sementara.

        File belum dibuat di sini. Hanya menghasilkan lokasi
        yang aman pada temporary directory OS.
        """
        temp_dir = tempfile.gettempdir()

        fd, path = tempfile.mkstemp(
            prefix=prefix,
            suffix=".pdf",
            dir=temp_dir,
        )

        os.close(fd)

        try:
            os.remove(path)
        except OSError:
            pass

        return path

    def open_pdf(self, pdf_path: str) -> None:
        """
        Membuka PDF menggunakan aplikasi default OS.
        Cocok digunakan untuk preview.
        """
        if not pdf_path or not os.path.isfile(pdf_path):
            raise PrinterError(
                "File PDF tidak ditemukan."
            )

        try:
            system = platform.system()

            if system == "Windows":
                os.startfile(pdf_path)

            elif system == "Darwin":
                subprocess.Popen(
                    ["open", pdf_path]
                )

            else:
                subprocess.Popen(
                    ["xdg-open", pdf_path]
                )

        except Exception as exc:
            log_error(
                "Printer.open_pdf gagal.\n"
                f"File: {pdf_path}\n"
                f"Error: {exc}"
            )

            raise PrinterError(
                "PDF berhasil dibuat tetapi tidak dapat dibuka."
            ) from exc

    def delete_temp_pdf(
        self,
        pdf_path: Optional[str],
    ) -> None:
        """
        Menghapus PDF sementara.

        Kegagalan penghapusan sengaja diabaikan karena file temporary
        tidak boleh menyebabkan aplikasi crash.
        """
        if not pdf_path:
            return

        try:
            if os.path.isfile(pdf_path):
                os.remove(pdf_path)
        except OSError:
            pass

    # =========================================================
    # DOCUMENT BUILDER
    # =========================================================

    def _build_document(
        self,
        document_type: str,
        data: Dict[str, Any],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        builders = {
            "sale": self._build_sale_document,
            "purchase": self._build_purchase_document,
            "debt": self._build_debt_document,
            "payment": self._build_payment_document,
            "customer_history": self._build_customer_history_document,
            "monthly_report": self._build_monthly_report_document,
        }

        builder = builders.get(document_type)

        if builder is None:
            raise PrinterError(
                f"Jenis dokumen tidak dikenal: {document_type}"
            )

        return builder(data, styles)

    # =========================================================
    # SALE
    # =========================================================

    def _build_sale_document(
        self,
        data: Dict[str, Any],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        sale = data.get("sale") or data

        details = (
            data.get("details")
            or data.get("items")
            or []
        )

        elements = self._build_header(
            "NOTA PENJUALAN",
            [
                (
                    "No. Transaksi",
                    sale.get("transaction_number") or "Transaksi Lama",
                ),
                ("Tanggal", self._date_text(sale.get("transaction_date"))),
            ],
            styles,
        )

        elements.append(
            self._build_items_table("Harga", details, styles)
        )
        elements.append(Spacer(1, SECTION_GAP))

        elements.append(
            self._build_summary(
                [
                    ("Total", self._money(sale.get("total_amount")), True),
                    ("Dibayar", self._money(sale.get("paid_amount")), False),
                    (
                        "Kembalian",
                        self._money(sale.get("change_amount")),
                        False,
                    ),
                ],
                styles,
            )
        )

        self._append_notes(elements, sale.get("notes"), styles)

        return elements

    # =========================================================
    # PURCHASE
    # =========================================================

    def _build_purchase_document(
        self,
        data: Dict[str, Any],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        details = (
            data.get("details")
            or data.get("items")
            or []
        )

        elements = self._build_header(
            "NOTA PEMBELIAN",
            [
                (
                    "No. Transaksi",
                    data.get("transaction_number") or "Transaksi Lama",
                ),
                ("Tanggal", self._date_text(data.get("transaction_date"))),
                (
                    "Supplier",
                    data.get("supplier_name") or "Tidak ada supplier",
                ),
            ],
            styles,
        )

        elements.append(
            self._build_items_table("Harga Beli", details, styles)
        )
        elements.append(Spacer(1, SECTION_GAP))

        elements.append(
            self._build_summary(
                [
                    (
                        "Total Pembelian",
                        self._money(data.get("total_amount")),
                        True,
                    ),
                ],
                styles,
            )
        )

        self._append_notes(elements, data.get("notes"), styles)

        return elements

    # =========================================================
    # DEBT
    # =========================================================

    def _build_debt_document(
        self,
        data: Dict[str, Any],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        details = (
            data.get("details")
            or data.get("items")
            or []
        )

        elements = self._build_header(
            "NOTA HUTANG",
            [
                (
                    "No. Transaksi",
                    data.get("transaction_number") or "Transaksi Lama",
                ),
                ("Tanggal", self._date_text(data.get("transaction_date"))),
                ("Pelanggan", data.get("customer_name") or "-"),
            ],
            styles,
        )

        elements.append(
            self._build_items_table("Harga", details, styles)
        )
        elements.append(Spacer(1, SECTION_GAP))

        elements.append(
            self._build_summary(
                [
                    (
                        "Total Hutang",
                        self._money(data.get("total_amount")),
                        True,
                    ),
                ],
                styles,
            )
        )

        self._append_notes(elements, data.get("notes"), styles)

        return elements

    # =========================================================
    # PAYMENT
    # =========================================================

    def _build_payment_document(
        self,
        data: Dict[str, Any],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        elements = self._build_header(
            "BUKTI PEMBAYARAN HUTANG",
            [
                ("Tanggal", self._date_text(data.get("payment_date"))),
                ("Pelanggan", data.get("customer_name") or "-"),
            ],
            styles,
        )

        elements.append(
            self._build_summary(
                [
                    (
                        "Jumlah Pembayaran",
                        self._money(data.get("amount")),
                        True,
                    ),
                    (
                        "Total Hutang Saat Itu",
                        self._money(data.get("total_debt_at_payment")),
                        False,
                    ),
                    (
                        "Sisa Hutang Saat Itu",
                        self._money(data.get("remaining_debt_at_payment")),
                        True,
                    ),
                ],
                styles,
            )
        )

        self._append_notes(elements, data.get("notes"), styles)

        return elements

    # =========================================================
    # CUSTOMER HISTORY
    # =========================================================

    def _build_customer_history_document(
        self,
        data: Dict[str, Any],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        """
        Membuat laporan seluruh riwayat hutang dan pembayaran
        satu pelanggan dengan sisa hutang berjalan.

        Timeline sumber diasumsikan terbaru -> terlama.
        Saldo dihitung terlama -> terbaru, lalu ditampilkan
        kembali terbaru -> terlama.
        """
        elements = self._build_header(
            "RIWAYAT HUTANG PELANGGAN",
            [("Pelanggan", data.get("customer_name") or "-")],
            styles,
        )

        timeline = list(data.get("timeline") or [])

        # -----------------------------------------------------
        # Saldo berjalan
        # -----------------------------------------------------

        running_balance = 0
        balance_map = {}

        for entry in reversed(timeline):
            entry_type = entry.get("type") or "-"
            amount = entry.get("amount", 0) or 0

            if entry_type == "Hutang":
                running_balance += amount

            elif entry_type == "Pembayaran":
                running_balance -= amount

            balance_map[id(entry)] = running_balance

        # -----------------------------------------------------
        # Ringkasan
        # -----------------------------------------------------

        elements.append(
            self._build_summary(
                [
                    ("Total Hutang", self._money(data.get("total_debt")), False),
                    (
                        "Total Pembayaran",
                        self._money(data.get("total_paid")),
                        False,
                    ),
                    ("Sisa Hutang", self._money(data.get("sisa")), True),
                ],
                styles,
            )
        )

        elements.append(Spacer(1, SECTION_GAP))

        # -----------------------------------------------------
        # Tabel riwayat
        # -----------------------------------------------------

        rows = [
            [
                Paragraph("Tanggal", styles["table_header"]),
                Paragraph("Jenis", styles["table_header_center"]),
                Paragraph("Keterangan", styles["table_header"]),
                Paragraph("Nominal", styles["table_header_right"]),
                Paragraph("Sisa Hutang", styles["table_header_right"]),
            ]
        ]

        for entry in timeline:
            entry_type = entry.get("type") or "-"
            amount = entry.get("amount", 0) or 0

            if entry_type == "Hutang":
                description = (
                    entry.get("transaction_number") or "Transaksi Lama"
                )
            elif entry_type == "Pembayaran":
                description = "Pembayaran"
            else:
                description = "-"

            rows.append(
                [
                    Paragraph(
                        self._safe_text(
                            format_date_indonesia(entry.get("date"))
                        ),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        self._safe_text(entry_type),
                        styles["table_cell_center"],
                    ),
                    Paragraph(
                        self._safe_text(description),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        self._safe_text(
                            self._signed_amount(entry_type, amount)
                        ),
                        styles["table_cell_right"],
                    ),
                    Paragraph(
                        self._safe_text(
                            format_rupiah(balance_map.get(id(entry), 0))
                        ),
                        styles["table_cell_right"],
                    ),
                ]
            )

        if not timeline:
            rows.append(
                [
                    Paragraph("-", styles["table_cell"]),
                    Paragraph("-", styles["table_cell_center"]),
                    Paragraph(
                        "Belum ada riwayat transaksi.",
                        styles["table_cell"],
                    ),
                    Paragraph("-", styles["table_cell_right"]),
                    Paragraph(
                        self._money(data.get("sisa")),
                        styles["table_cell_right"],
                    ),
                ]
            )

        table = Table(
            rows,
            colWidths=HISTORY_COLUMNS,
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(self._grid_style())

        elements.append(table)

        return elements

    # =========================================================
    # MONTHLY REPORT
    # =========================================================

    def _build_monthly_report_document(
        self,
        data: Dict[str, Any],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        """
        Laporan bulanan. `data` adalah hasil
        ReportModel.get_monthly_report().

        Susunan: header, kotak ringkasan (2 x 2 + saldo), catatan,
        lalu tabel detail bergaris selang-seling. Halaman berikutnya
        mendapat judul berjalan di bagian atas.
        """
        try:
            month_name = BULAN_INDONESIA[int(data.get("month", 1)) - 1]
        except (IndexError, TypeError, ValueError):
            month_name = str(data.get("month", "-"))

        period = f"{month_name} {data.get('year', '')}".strip()

        self._running_header = (
            f"{self.store_name} - Laporan Bulanan {period}"
        )

        elements = self._build_header(
            "LAPORAN BULANAN",
            [("Periode", period)],
            styles,
        )

        # -----------------------------------------------------
        # Ringkasan: kotak 2 x 2 + saldo saat ini
        # -----------------------------------------------------

        def tile(label, value, big=False):
            return [
                Paragraph(self._escape_text(label), styles["tile_label"]),
                Paragraph(
                    self._escape_text(value),
                    styles["tile_value_big" if big else "tile_value"],
                ),
            ]

        summary = Table(
            [
                [
                    tile(
                        "Total Hutang Bulan Ini",
                        self._money(data.get("total_debt_month")),
                    ),
                    tile(
                        "Total Pembayaran Bulan Ini",
                        self._money(data.get("total_payment_month")),
                    ),
                ],
                [
                    tile(
                        "Jumlah Transaksi Hutang",
                        str(data.get("count_debt_transactions", 0)),
                    ),
                    tile(
                        "Jumlah Transaksi Pembayaran",
                        str(data.get("count_payment_transactions", 0)),
                    ),
                ],
                [
                    tile(
                        "Saldo Saat Ini (Seluruh Pelanggan)",
                        self._money(data.get("current_outstanding_balance")),
                        big=True,
                    ),
                    "",
                ],
            ],
            colWidths=STAT_COLUMNS,
            hAlign="LEFT",
        )
        summary.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.8, COLOR_TEXT),
                    ("INNERGRID", (0, 0), (-1, 1), 0.5, COLOR_GRID),
                    ("LINEABOVE", (0, 2), (-1, 2), 0.8, COLOR_TEXT),
                    ("BACKGROUND", (0, 2), (-1, 2), COLOR_HEADER_BG),
                    ("SPAN", (0, 2), (1, 2)),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("TOPPADDING", (0, 0), (-1, -1), 7),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                ]
            )
        )

        elements.append(summary)
        elements.append(Spacer(1, 2 * mm))

        elements.append(
            Paragraph(
                "Catatan: angka aktivitas di atas hanya untuk bulan ini. "
                "Saldo saat ini mencakup seluruh transaksi, tidak dibatasi bulan.",
                styles["muted"],
            )
        )

        elements.append(Spacer(1, SECTION_GAP))

        # -----------------------------------------------------
        # Detail transaksi
        # -----------------------------------------------------

        details = data.get("details") or []

        section_title = "Detail Transaksi Bulan Ini"

        if details:
            section_title += f" ({len(details)} transaksi)"

        elements.append(Paragraph(section_title, styles["section_title"]))
        elements.append(Spacer(1, 2 * mm))

        rows = [
            [
                Paragraph("Tanggal", styles["table_header"]),
                Paragraph("Pelanggan", styles["table_header"]),
                Paragraph("Jenis", styles["table_header"]),
                Paragraph("Nominal", styles["table_header_right"]),
            ]
        ]

        for item in details:
            entry_type = item.get("type") or "-"

            rows.append(
                [
                    Paragraph(
                        self._safe_text(
                            format_date_indonesia(item.get("date"))
                        ),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        self._safe_text(item.get("customer_name")),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        self._safe_text(entry_type),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        self._safe_text(
                            self._signed_amount(
                                entry_type,
                                item.get("amount", 0) or 0,
                            )
                        ),
                        styles["table_cell_right"],
                    ),
                ]
            )

        grid = self._grid_style(zebra=bool(details))

        if not details:
            rows.append(
                [
                    Paragraph(
                        "Tidak ada transaksi pada bulan ini.",
                        styles["table_cell"],
                    ),
                    "",
                    "",
                    "",
                ]
            )
            grid.add("SPAN", (0, 1), (-1, 1))

        table = Table(
            rows,
            colWidths=REPORT_COLUMNS,
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(grid)

        elements.append(table)

        return elements

    # =========================================================
    # COMMON BLOCKS
    # =========================================================

    def _build_header(
        self,
        title: str,
        info_rows: List[tuple],
        styles: Dict[str, ParagraphStyle],
    ) -> List[Any]:
        """
        Header seragam untuk semua dokumen:
        nama warung, judul dokumen, garis, lalu blok info
        (label di kiri, nilai di kanan).
        """
        elements = [
            Paragraph(
                self._escape_text(self.store_name),
                styles["store_name"],
            ),
            Paragraph(
                self._escape_text(title),
                styles["document_title"],
            ),
            Spacer(1, SMALL_GAP),
            HRFlowable(
                width="100%",
                thickness=0.8,
                color=COLOR_TEXT,
                spaceBefore=0,
                spaceAfter=0,
            ),
            Spacer(1, SMALL_GAP),
        ]

        if info_rows:
            elements.append(self._info_table(info_rows, styles))

        elements.append(Spacer(1, SECTION_GAP))

        return elements

    def _info_table(
        self,
        rows: List[tuple],
        styles: Dict[str, ParagraphStyle],
    ) -> Table:
        data = [
            [
                Paragraph(
                    f"<b>{self._escape_text(label)}</b>",
                    styles["normal"],
                ),
                Paragraph(
                    self._escape_text(value),
                    styles["normal"],
                ),
            ]
            for label, value in rows
        ]

        table = Table(
            data,
            colWidths=[
                INFO_LABEL_WIDTH,
                CONTENT_WIDTH - INFO_LABEL_WIDTH,
            ],
            hAlign="LEFT",
        )

        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]
            )
        )

        return table

    def _build_items_table(
        self,
        price_title: str,
        details: List[Dict[str, Any]],
        styles: Dict[str, ParagraphStyle],
    ) -> Table:
        rows = [
            [
                Paragraph("Barang", styles["table_header"]),
                Paragraph("Qty", styles["table_header_right"]),
                Paragraph(price_title, styles["table_header_right"]),
                Paragraph("Subtotal", styles["table_header_right"]),
            ]
        ]

        for item in details:
            rows.append(
                [
                    Paragraph(
                        self._safe_text(item.get("product_name")),
                        styles["table_cell"],
                    ),
                    Paragraph(
                        self._safe_text(item.get("quantity", 0)),
                        styles["table_cell_right"],
                    ),
                    Paragraph(
                        self._money(item.get("price")),
                        styles["table_cell_right"],
                    ),
                    Paragraph(
                        self._money(item.get("subtotal")),
                        styles["table_cell_right"],
                    ),
                ]
            )

        table = Table(
            rows,
            colWidths=ITEM_COLUMNS,
            repeatRows=1,
            hAlign="LEFT",
        )
        table.setStyle(self._grid_style())

        return table

    def _build_summary(
        self,
        rows: List[tuple],
        styles: Dict[str, ParagraphStyle],
    ) -> Table:
        """
        Blok ringkasan rata kanan.

        rows: list of (label, nilai_teks, utama).
        Baris utama dicetak lebih besar; bila bukan baris pertama,
        diberi garis tipis di atasnya.
        """
        data = []
        commands = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]

        for index, (label, value, primary) in enumerate(rows):
            data.append(
                [
                    Paragraph(
                        self._escape_text(label),
                        styles["summary_label_big" if primary else "summary_label"],
                    ),
                    Paragraph(
                        self._escape_text(value),
                        styles["summary_value_big" if primary else "summary_value"],
                    ),
                ]
            )

            if primary and index > 0:
                commands.append(
                    ("LINEABOVE", (0, index), (-1, index), 0.8, COLOR_TEXT)
                )

        table = Table(
            data,
            colWidths=[
                SUMMARY_LABEL_WIDTH,
                SUMMARY_WIDTH - SUMMARY_LABEL_WIDTH,
            ],
            hAlign="RIGHT",
        )
        table.setStyle(TableStyle(commands))

        return table

    @staticmethod
    def _grid_style(zebra: bool = False) -> TableStyle:
        """
        Gaya tabel data: kisi abu-abu, header berlatar abu muda.
        zebra=True memberi warna selang-seling pada baris isi
        (untuk tabel panjang).
        """
        commands = [
            ("GRID", (0, 0), (-1, -1), 0.5, COLOR_GRID),
            ("BACKGROUND", (0, 0), (-1, 0), COLOR_HEADER_BG),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("RIGHTPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("TOPPADDING", (0, 0), (-1, -1), CELL_PADDING),
            ("BOTTOMPADDING", (0, 0), (-1, -1), CELL_PADDING),
        ]

        if zebra:
            commands.append(
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, COLOR_ZEBRA],
                )
            )

        return TableStyle(commands)

    def _append_notes(
        self,
        elements: List[Any],
        notes: Optional[str],
        styles: Dict[str, ParagraphStyle],
    ) -> None:
        if not notes:
            return

        elements.append(Spacer(1, SECTION_GAP))

        elements.append(
            Paragraph("<b>Catatan</b>", styles["normal"])
        )

        elements.append(
            Paragraph(
                self._escape_text(notes).replace("\n", "<br/>"),
                styles["normal"],
            )
        )

    def _draw_later_page(self, canvas_obj, doc) -> None:
        """Halaman kedua dan seterusnya: judul berjalan + footer."""
        self._draw_running_header(canvas_obj)
        self._draw_footer(canvas_obj, doc)

    def _draw_running_header(self, canvas_obj) -> None:
        if not self._running_header:
            return

        text = self._running_header
        max_width = A4[0] - (PAGE_MARGIN * 2)

        while len(text) > 4 and stringWidth(text, FONT, 8) > max_width:
            text = text[:-4] + "..."

        canvas_obj.saveState()
        canvas_obj.setFont(FONT, 8)
        canvas_obj.setFillColor(COLOR_MUTED)

        y = A4[1] - 9 * mm

        canvas_obj.drawString(PAGE_MARGIN, y, text)

        canvas_obj.setStrokeColor(COLOR_GRID)
        canvas_obj.setLineWidth(0.4)
        canvas_obj.line(
            PAGE_MARGIN,
            y - 2 * mm,
            A4[0] - PAGE_MARGIN,
            y - 2 * mm,
        )

        canvas_obj.restoreState()

    def _draw_footer(self, canvas_obj, doc) -> None:
        """Footer di setiap halaman: waktu cetak (kiri), nomor halaman (kanan)."""
        canvas_obj.saveState()
        canvas_obj.setFont(FONT, 7.5)
        canvas_obj.setFillColor(COLOR_MUTED)

        y = 8 * mm

        canvas_obj.drawString(
            PAGE_MARGIN,
            y,
            f"Dicetak {self._printed_at}",
        )
        canvas_obj.drawRightString(
            A4[0] - PAGE_MARGIN,
            y,
            f"Halaman {canvas_obj.getPageNumber()}",
        )

        canvas_obj.restoreState()

    # =========================================================
    # STYLES
    # =========================================================

    @staticmethod
    def _build_styles() -> Dict[str, ParagraphStyle]:
        base = getSampleStyleSheet()

        def style(name, **kwargs):
            options = {
                "parent": base["Normal"],
                "fontName": FONT,
                "fontSize": 9,
                "leading": 12,
                "textColor": COLOR_TEXT,
            }
            options.update(kwargs)
            return ParagraphStyle(name, **options)

        return {
            "normal": style("WHNormal"),
            "muted": style(
                "WHMuted",
                fontName=FONT_ITALIC,
                fontSize=8,
                leading=10,
                textColor=COLOR_MUTED,
            ),
            "store_name": style(
                "WHStoreName",
                fontName=FONT_BOLD,
                fontSize=16,
                leading=20,
                alignment=TA_CENTER,
                spaceAfter=2,
            ),
            "document_title": style(
                "WHDocumentTitle",
                fontName=FONT_BOLD,
                fontSize=12,
                leading=15,
                alignment=TA_CENTER,
            ),
            "section_title": style(
                "WHSectionTitle",
                fontName=FONT_BOLD,
                fontSize=10,
                leading=13,
            ),
            "table_header": style(
                "WHTableHeader",
                fontName=FONT_BOLD,
                fontSize=8,
                leading=10,
                alignment=TA_LEFT,
            ),
            "table_header_center": style(
                "WHTableHeaderCenter",
                fontName=FONT_BOLD,
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
            ),
            "table_header_right": style(
                "WHTableHeaderRight",
                fontName=FONT_BOLD,
                fontSize=8,
                leading=10,
                alignment=TA_RIGHT,
            ),
            "table_cell": style(
                "WHTableCell",
                fontSize=8,
                leading=10,
                alignment=TA_LEFT,
            ),
            "table_cell_center": style(
                "WHTableCellCenter",
                fontSize=8,
                leading=10,
                alignment=TA_CENTER,
            ),
            "table_cell_right": style(
                "WHTableCellRight",
                fontSize=8,
                leading=10,
                alignment=TA_RIGHT,
            ),
            "tile_label": style(
                "WHTileLabel",
                fontSize=8,
                leading=10,
                textColor=COLOR_MUTED,
            ),
            "tile_value": style(
                "WHTileValue",
                fontName=FONT_BOLD,
                fontSize=13,
                leading=17,
            ),
            "tile_value_big": style(
                "WHTileValueBig",
                fontName=FONT_BOLD,
                fontSize=16,
                leading=20,
            ),
            "summary_label": style("WHSummaryLabel"),
            "summary_value": style(
                "WHSummaryValue",
                alignment=TA_RIGHT,
            ),
            "summary_label_big": style(
                "WHSummaryLabelBig",
                fontName=FONT_BOLD,
                fontSize=11,
                leading=14,
            ),
            "summary_value_big": style(
                "WHSummaryValueBig",
                fontName=FONT_BOLD,
                fontSize=12,
                leading=15,
                alignment=TA_RIGHT,
            ),
        }

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _money(value: Any) -> str:
        return format_rupiah(value or 0)

    @staticmethod
    def _date_text(value: Any) -> str:
        return format_date_indonesia(value or "-")

    @staticmethod
    def _signed_amount(entry_type: str, amount: Any) -> str:
        if entry_type == "Hutang":
            sign = "+ "
        elif entry_type == "Pembayaran":
            sign = "- "
        else:
            sign = ""

        return f"{sign}{format_rupiah(amount or 0)}"

    @staticmethod
    def _safe_text(value: Any) -> str:
        if value is None:
            return "-"

        return Printer._escape_text(
            str(value)
        )

    @staticmethod
    def _escape_text(value: Any) -> str:
        if value is None:
            return "-"

        text = str(value)

        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )

    @staticmethod
    def _get_document_title(
        document_type: str,
    ) -> str:
        titles = {
            "sale": "Nota Penjualan",
            "purchase": "Nota Pembelian",
            "debt": "Nota Hutang",
            "payment": "Bukti Pembayaran Hutang",
            "customer_history": "Riwayat Hutang Pelanggan",
            "monthly_report": "Laporan Bulanan",
        }

        return titles.get(
            document_type,
            "Dokumen Warung Hutang",
        )


def create_printer(store_name: Optional[str] = None) -> Printer:
    """
    Factory sederhana agar pemanggilan dari UI lebih ringkas.
    Jika store_name tidak diberikan, nama warung diambil dari Pengaturan.
    """
    return Printer(store_name=store_name)