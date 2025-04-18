from pathlib import Path
import os
from imagededup.methods import CNN
from utils import convert_heic_to_jpg
from logger import logger

# Initialize CNN encoder - will download model on first use
cnn_encoder = CNN()

class ImageDuplicateService:
    def __init__(self, upload_dir):
        self.upload_dir = upload_dir

    def detect_duplicates_in_dir(self, user_dir):
        """
        Detect duplicate images in user directory using CNN-based image deduplication
        """
        try:
            target_dir = self.upload_dir / user_dir
            
            if not target_dir.exists() or not any(target_dir.iterdir()):
                return []

            has_standard_images = False
            has_heic_images = False
            original_filenames = {}

            for img_path in target_dir.glob("*"):
                if not img_path.is_file():
                    continue

                if img_path.suffix.lower() in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']:
                    has_standard_images = True
                    original_filenames[img_path.name] = img_path.name
                elif img_path.suffix.lower() in ['.heic']:
                    has_heic_images = True
                    jpg_path = img_path.with_suffix('.jpg')
                    if convert_heic_to_jpg(img_path, jpg_path):
                        has_standard_images = True
                        original_filenames[jpg_path.name] = img_path.name

            if not has_standard_images:
                if has_heic_images:
                    return {"error": "HEIC images found but couldn't be converted. Please install pillow-heif or ImageMagick."}
                return []

            duplicates = cnn_encoder.find_duplicates(image_dir=target_dir, scores=True)

            connected_images = {}
            for key, value_list in duplicates.items():
                original_key = original_filenames.get(key, key)
                if original_key not in connected_images:
                    connected_images[original_key] = set()

                for filename, score in value_list:
                    original_filename = original_filenames.get(filename, filename)
                    connected_images[original_key].add(original_filename)

                    if original_filename not in connected_images:
                        connected_images[original_filename] = set()
                    connected_images[original_filename].add(original_key)

            visited = set()
            groups = []

            def dfs(node, component):
                visited.add(node)
                component.add(node)
                for neighbor in connected_images.get(node, []):
                    if neighbor not in visited:
                        dfs(neighbor, component)

            for node in connected_images:
                if node not in visited:
                    component = set()
                    dfs(node, component)
                    if len(component) > 1:
                        groups.append(list(component))

            return groups
        except RuntimeError as e:
            if "empty TensorList" in str(e):
                return {"error": "No valid images could be processed. Please check image formats."}
            logger.error(f"Error processing images: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Error detecting duplicates: {str(e)}")
            raise

    async def process_uploaded_files(self, user_id, files):
        """
        Process uploaded files, create user directory and handle image files
        """
        user_dir = Path(user_id)
        target_dir = self.upload_dir / user_dir
        target_dir.mkdir(exist_ok=True, parents=True)

        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.heic']
        uploaded_files = 0
        skipped_files = 0
        
        # Process files
        for file in files:
            _, extension = os.path.splitext(file.filename.lower())
            if extension not in valid_extensions:
                skipped_files += 1
                continue
            
            file_path = target_dir / file.filename
            with open(file_path, "wb") as buffer:
                import shutil
                shutil.copyfileobj(file.file, buffer)
            uploaded_files += 1
            
        return uploaded_files, skipped_files