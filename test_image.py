from PIL import Image, ImageDraw, ImageFont
import os

def test_image_processing():
    """Test the image processing functionality"""
    print("Creating test images...")
    
    # Create a blank main image (500x500)
    main_img = Image.new('RGBA', (500, 500), color=(255, 255, 255, 255))
    
    # Create a smaller reference image (60x60)
    ref_img = Image.new('RGBA', (60, 60), color=(255, 0, 0, 255))
    
    # Calculate the center position
    main_width, main_height = main_img.size
    ref_width, ref_height = ref_img.size
    
    x_position = (main_width - ref_width) // 2
    y_position = (main_height - ref_height) // 2
    
    # Paste the reference image in the center
    main_img.paste(ref_img, (x_position, y_position), mask=ref_img)
    
    # Add text
    draw = ImageDraw.Draw(main_img)
    
    # Try to load a font, use default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()
    
    name = "Test User"
    text_width = 0
    
    # Check Pillow version for text width calculation
    if hasattr(draw, "textlength"):
        text_width = draw.textlength(name, font=font)
        print("Using draw.textlength method")
    elif hasattr(font, "getlength"):
        text_width = font.getlength(name)
        print("Using font.getlength method")
    else:
        # Fallback for older Pillow versions
        text_width = font.getsize(name)[0]
        print("Using font.getsize method")
    
    name_position = ((main_width - text_width) // 2, main_height - 30)
    
    # Add white text with black outline
    draw.text((name_position[0]-1, name_position[1]-1), name, font=font, fill="black")
    draw.text((name_position[0]+1, name_position[1]-1), name, font=font, fill="black")
    draw.text((name_position[0]-1, name_position[1]+1), name, font=font, fill="black")
    draw.text((name_position[0]+1, name_position[1]+1), name, font=font, fill="black")
    draw.text(name_position, name, font=font, fill="white")
    
    # Save the test image
    main_img.save("test_output.png")
    print(f"Test image saved as 'test_output.png' in {os.getcwd()}")
    print("Image processing test successful!")

if __name__ == "__main__":
    test_image_processing() 