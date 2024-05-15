from matplotlib import pyplot as plt
from AI.extract_data.get_problem_data import get_response_from_claude
from AI.image_segmentation.crop_pieces import model_predict
from cheada_fastapi.cheada.domain.textBook_preprocessing.dto.ProblemInfoDto import ProblemInfoDto
from cheada_fastapi.cheada.domain.textBook_preprocessing.service.image_service import upload_image_to_s3

import os, fitz, cv2
import numpy as np

def determine_vertical_line(pix, index):
	image_bytes = pix.samples
	image = np.frombuffer(image_bytes, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
	if pix.n == 4:
		image = cv2.cvtColor(image, cv2.COLOR_RGBA2BGR)
	gray_img = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
	ret, binary_image = cv2.threshold(gray_img, 240, 255, cv2.THRESH_BINARY)
	height, width = binary_image.shape
	center = width // 2
	thickness = 20 # 검사할 선의 두께
	center_line = binary_image[100:height-100, center-thickness//2:center+thickness//2]
	
	kernel = np.ones((5, 5), np.uint8)
	opening = cv2.morphologyEx(center_line, cv2.MORPH_OPEN, kernel)
	
	for r in range(20, opening.shape[0], 20):
		piece = opening[r-20:r, :]
		y_coords, x_coords = np.where(piece == 0)

		if y_coords.size == 0 or np.max(piece) == 0:
			return

		prev_y, prev_x = y_coords[0], x_coords[0]
		for y in y_coords:
			if abs(y-prev_y) >= 5:
				return
			prev_y = y

	# plt.title(f"{index}")
	# plt.imshow(opening, cmap='gray_r')
	# plt.show()
	return True

	
def convert_pdf_to_png(pdf_file, output_folder, pdf_page_number = 0):
	pure_file_name = os.path.basename(pdf_file)[:-4].replace(" ", "")

	if not os.path.exists(output_folder):
		os.mkdir(output_folder)
	
	doc = fitz.open(pdf_file)

	
	try:
		if pdf_page_number == 0: # pdf_page_number 특정 값 미지정 시, 전체 변환
			for i, page in enumerate(doc):
				img = page.get_pixmap()   # 이미지 변환
				if determine_vertical_line(pix=img, index=i+1):
					print(i+1)
					img.save(output_folder + "\\" + pure_file_name + f'_{i}th_problem_page.png') # 변환된 이미지 저장
				
			print('전체 변환')
		elif pdf_page_number != 0:
			page = doc.load_page(pdf_page_number - 1) # 특정 페이지 가져오기
			i = pdf_page_number
			img = page.get_pixmap()   # 이미지 변환
			img.save(output_folder + "\\" + pure_file_name + f'_{i}_only_output.png') # 변환된 이미지 저장
			
			print(pdf_page_number, '페이지 변환')

		
	except ValueError:
		print('Error: page not in document')
    

def start_preprocessing(fileName, local_textbook_dir, temp_page_storage, temp_problem_storage):
    print("\nstart preprocess thread\n")
    # 1. pdf를 png로 바꾸고
    if os.path.exists(temp_page_storage):
        print("해당 문제집은 이미 이미지로 변환된 상태입니다.")
    else:
        print('변환')
        convert_pdf_to_png(pdf_file=f"{local_textbook_dir}\\{fileName}", output_folder=temp_page_storage)
    
    # 2. png마다 문제 crop하고 추출
    print("2. png마다 문제 crop하고 추출")
    model_predict(image_dir=temp_page_storage, save_location=temp_problem_storage)
    
    # 3. crop한 문제 s3에 업로드
    for i, page_img in enumerate(os.listdir(rf"{temp_page_storage}")): 
        response = get_response_from_claude(image_path=f"{temp_page_storage}\\{page_img}", subject="수학 II")
        print(response)
        if i == 3: break
    