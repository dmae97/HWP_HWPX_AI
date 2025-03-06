import os
import sys
import tempfile
import pyhwpx

def test_hwp_extraction(file_path):
    """
    Test HWP text extraction functionality.
    
    Args:
        file_path (str): Path to the HWP file to test.
    """
    print(f"Testing HWP extraction on file: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return
    
    try:
        # Open the HWP file
        hwp = pyhwpx.open(file_path)
        
        # Print basic information
        print(f"Number of pages: {len(hwp)}")
        
        # Extract and print text from each page
        for i in range(len(hwp)):
            print(f"\n--- Page {i+1} ---")
            page_text = hwp[i].text
            # Print first 200 characters of each page
            print(page_text[:200] + "..." if len(page_text) > 200 else page_text)
        
        print("\nHWP extraction test completed successfully.")
    except Exception as e:
        print(f"Error during HWP extraction: {str(e)}")

if __name__ == "__main__":
    # Check if file path is provided as command line argument
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        test_hwp_extraction(file_path)
    else:
        print("Usage: python test_hwp.py <path_to_hwp_file>")
        print("Example: python test_hwp.py ./data/sample.hwp") 