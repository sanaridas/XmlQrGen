import tkinter as tk
from tkinter import filedialog
import xml.etree.ElementTree as ET
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
import io

def select_xml_file():
    """Opens a file dialog for the user to select an XML file."""
    root = tk.Tk()
    root.withdraw()  # Hide the main Tkinter window
    file_path = filedialog.askopenfilename(
        title="Select XML File",
        filetypes=(("XML files", "*.xml"), ("All files", "*.*"))
    )
    return file_path

def extract_data_from_xml(xml_file_path):
    """
    Parses the XML file and extracts zbpName attributes based on the specified criteria,
    excluding names containing "gl".
    Args:
        xml_file_path (str): The path to the XML file.
    Returns:
        list: A list of zbpName strings to be encoded in QR codes.
    """
    zbp_names_to_encode = []
    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
        
        for protection_point in root.findall('.//protectionPoint'):
            zbp_name = protection_point.get('zbpName')
            ordered_zbp = protection_point.find('orderedZbp')
            
            if zbp_name and ordered_zbp is not None:
                deletion_type = ordered_zbp.get('orderedZbpDeletionType')
                # Filter condition: must be "kein Abbau" AND "gl" not in zbpName
                if deletion_type == "kein Abbau" and "gl" not in zbp_name:
                    zbp_names_to_encode.append(zbp_name)
                    
    except ET.ParseError as e:
        print(f"Error parsing XML file: {e}")
        return []
    except FileNotFoundError:
        print(f"Error: XML file not found at {xml_file_path}")
        return []
    return zbp_names_to_encode

def create_pdf_with_qrcodes(data_list, output_filename="qrcodes_output.pdf"):
    """
    Creates a PDF document with QR codes and labels, with improved page break logic.
    Args:
        data_list (list): A list of strings, where each string is the data to be
                          encoded in a QR code and used as its label.
        output_filename (str): The name of the PDF file to be generated.
    """
    if not data_list:
        print("No data to generate QR codes for. PDF will not be created.")
        return

    c = canvas.Canvas(output_filename, pagesize=A4)
    a4_width, a4_height = A4

    # Define layout constants
    margin = 1.5 * cm
    qr_size = 3 * cm
    label_area_height = 1 * cm # Includes padding for the label
    items_per_row = 5
    
    usable_width = a4_width - (2 * margin)
    horizontal_gap = 0
    if items_per_row > 1:
        horizontal_gap = (usable_width - (items_per_row * qr_size)) / (items_per_row - 1)
    
    start_x_first_item = margin
    if items_per_row == 1: # Center single item
        start_x_first_item = margin + (usable_width - qr_size) / 2

    vertical_gap_between_rows = 0.5 * cm
    label_font_size = 8
    label_offset_y = 0.4 * cm # Distance from QR bottom to label text baseline

    # Initial drawing positions for the very first item on the first page
    # current_y_qr_bottom is the Y-coordinate for the BOTTOM of the QR code image
    current_y_qr_bottom = a4_height - margin - qr_size 
    current_x = start_x_first_item
    
    item_index_in_current_row = 0 # 0-indexed counter for items in the current row

    for index, data_string in enumerate(data_list):
        # 1. Determine if the current item starts a new row.
        #    This happens if item_index_in_current_row has reached items_per_row
        #    (meaning the previous item completed a row).
        if item_index_in_current_row == items_per_row:
            item_index_in_current_row = 0  # Reset for the new row
            current_x = start_x_first_item   # Reset X to the start of the row
            # Move Y down for the new row. This is the Y for the bottom of QRs in this new row.
            current_y_qr_bottom -= (qr_size + label_area_height + vertical_gap_between_rows)

        # 2. With current_y_qr_bottom set for the potential start of this item (either in an
        #    ongoing row or a new row), check if a page break is needed BEFORE drawing.
        #    The lowest point the item (QR + label) will occupy is current_y_qr_bottom - label_area_height.
        if current_y_qr_bottom - label_area_height < margin:
            c.showPage() # Finalize current page
            c.setFont("Helvetica", label_font_size) # Reset font for new page
            
            # Reset Y to the top for the first row on the new page
            current_y_qr_bottom = a4_height - margin - qr_size
            # Reset X and item_index_in_current_row as this item will start a new row on a new page
            current_x = start_x_first_item
            item_index_in_current_row = 0 
            # Note: If the item that triggered the new row (step 1) also triggers a page break,
            # current_y_qr_bottom will be correctly set to the top of the new page.

        # 3. Generate QR code image
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=2
        )
        qr.add_data(data_string)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white").convert('RGB')

        img_buffer = io.BytesIO()
        img.save(img_buffer, format="PNG")
        img_buffer.seek(0)
        
        # Draw QR code on PDF at current_x, current_y_qr_bottom
        c.drawImage(ImageReader(img_buffer), current_x, current_y_qr_bottom, 
                    width=qr_size, height=qr_size, preserveAspectRatio=True)

        # Draw label under QR code
        c.setFont("Helvetica", label_font_size)
        label_x_center = current_x + (qr_size / 2)
        label_y_baseline = current_y_qr_bottom - label_offset_y
        c.drawCentredString(label_x_center, label_y_baseline, data_string)
        
        # 4. Update X for the next item in the current row and increment row item counter
        current_x += (qr_size + horizontal_gap)
        item_index_in_current_row += 1

    c.save()
    print(f"PDF generated successfully: {output_filename}")

def main():
    xml_file = select_xml_file()
    if not xml_file:
        print("No XML file selected. Exiting.")
        return

    print(f"Selected XML file: {xml_file}")
    
    zbp_data = extract_data_from_xml(xml_file)
    
    if zbp_data:
        print(f"Found {len(zbp_data)} items to encode (after filtering):")
        # for item in zbp_data: # Optionally print all items
        #     print(f"  - {item}")
        create_pdf_with_qrcodes(zbp_data)
    else:
        print("No relevant data found in the XML file to generate QR codes (after filtering).")

if __name__ == "__main__":
    main()
