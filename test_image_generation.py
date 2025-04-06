from PIL import Image, ImageDraw, ImageFont
import os

def create_test_image():
    """Create a test image with a small icon in the center and text at the bottom"""
    print("Creating test image...")
    
    # Create main background image (500x500 blue background)
    main_img = Image.new('RGBA', (500, 500), (100, 150, 200, 255))
    print(f"Created main image: {main_img.size} mode={main_img.mode}")
    
    # Create reference image (60x60 red square)
    ref_img = Image.new('RGBA', (60, 60), (255, 0, 0, 255))
    print(f"Created reference image: {ref_img.size} mode={ref_img.mode}")
    
    # Calculate center position
    main_width, main_height = main_img.size
    ref_width, ref_height = ref_img.size
    x_position = (main_width - ref_width) // 2
    y_position = (main_height - ref_height) // 2
    print(f"Center position: ({x_position}, {y_position})")
    
    # Paste reference image onto main image
    main_img.paste(ref_img, (x_position, y_position), ref_img)
    print("Pasted reference image onto main image")
    
    # Add text at bottom
    draw = ImageDraw.Draw(main_img)
    font = ImageFont.load_default()
    name = "Test User"
    
    # Calculate text width for centering
    text_width = 0
    if hasattr(draw, "textlength"):
        text_width = draw.textlength(name, font=font)
    elif hasattr(font, "getlength"):
        text_width = font.getlength(name)
    else:
        text_width = font.getsize(name)[0]
    
    text_x = (main_width - text_width) // 2
    text_y = main_height - 30
    print(f"Text position: ({text_x}, {text_y})")
    
    # Add white text with black outline
    draw.text((text_x-1, text_y-1), name, fill="black", font=font)
    draw.text((text_x+1, text_y-1), name, fill="black", font=font)
    draw.text((text_x-1, text_y+1), name, fill="black", font=font)
    draw.text((text_x+1, text_y+1), name, fill="black", font=font)
    draw.text((text_x, text_y), name, fill="white", font=font)
    print("Added text to image")
    
    # Save image to file
    output_path = "test_output.png"
    main_img.save(output_path)
    
    # Check file size
    file_size = os.path.getsize(output_path)
    print(f"Saved test image to {output_path} ({file_size} bytes)")
    
    print("Test completed successfully!")
    
if __name__ == "__main__":
    create_test_image() 