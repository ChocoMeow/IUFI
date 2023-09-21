import os, torch, timm, faiss, io
import pandas as pd, numpy as np

from PIL import Image
from typing import Any
from tqdm import tqdm
from torchvision import transforms
from torch.autograd import Variable

def image_data_with_features_pkl(model_name: str) -> str:
    image_data_with_features_pkl = os.path.join('metadata-files/',f'{model_name}/','image_data_features.pkl')
    return image_data_with_features_pkl

def image_features_vectors_idx(model_name: str) -> str:
    image_features_vectors_idx = os.path.join('metadata-files/',f'{model_name}/','image_features_vectors.idx')
    return image_features_vectors_idx

class Load_Data:
    def from_folder(self, folder_list: list) -> list[str]:
        self.folder_list = folder_list
        image_path = []
        for folder in self.folder_list:
            for root, _, files in os.walk(folder):
                for file in files:
                    if file.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
                        image_path.append(os.path.join(root, file))
        return image_path

class Search_Setup:
    def __init__(self, image_list: list, model_name='vgg19', pretrained=True, image_count: int = None) -> None:
        self.model_name = model_name
        self.pretrained = pretrained
        self.image_data = pd.DataFrame()
        self.d = None
        if image_count==None:
            self.image_list = image_list
        else:
            self.image_list = image_list[:image_count]

        if f'metadata-files/{self.model_name}' not in os.listdir():
            try:
                os.makedirs(f'metadata-files/{self.model_name}')
            except Exception as e:
                pass

        # Load the pre-trained model and remove the last layer
        print("\033[91m Please Wait Model Is Loading or Downloading From Server!")
        base_model = timm.create_model(self.model_name, pretrained=self.pretrained)
        self.model = torch.nn.Sequential(*list(base_model.children())[:-1])
        self.model.eval()
        print(f"\033[92m Model Loaded Successfully: {model_name}")

    def _extract(self, img: Image.Image) -> float:
        # Resize and convert the image
        size = (224, 224)
        img_ratio = img.width / img.height
        ratio = size[0] / size[1]
        
        # The image is scaled/cropped vertically or horizontally depending on the ratio
        if ratio > img_ratio:
            # The image is scaled/cropped based on the width of the image
            img = img.resize((size[0], round(size[0] * img.height / img.width)))
            box = (0, (img.height - size[1]) / 2, img.width, (img.height + size[1]) / 2)
            img = img.crop(box)
        elif ratio < img_ratio:
            # The image is scaled/cropped based on the height of the image
            img = img.resize((round(size[1] * img.width / img.height), size[1]))
            box = ((img.width - size[0]) / 2, 0, (img.width + size[0]) / 2, img.height)
            img = img.crop(box)
        else :
            # If the image ratio is equal to the desired ratio it is resized without cropping
            img = img.resize((size[0], size[1]))
        img = img.convert('RGB')

        # Preprocess the image
        preprocess = transforms.Compose([
            transforms.ToTensor(),
            transforms.Normalize(mean=[0.485, 0.456, 0.406],std=[0.229,0.224, 0.225]),
        ])
        x = preprocess(img)
        x = Variable(torch.unsqueeze(x, dim=0).float(), requires_grad=False)

        # Extract features
        feature = self.model(x)
        feature = feature.data.numpy().flatten()
        return feature / np.linalg.norm(feature)

    def _get_feature(self, image_data: list) -> list[float | None]:
        self.image_data = image_data
        features = []
        for img_path in tqdm(self.image_data):  # Iterate through images
            # Extract features from the image
            try:
                feature = self._extract(img=Image.open(img_path))
                features.append(feature)
            except:
               # If there is an error, append None to the feature list
               features.append(None)
               continue
        return features

    def _start_feature_extraction(self):
        image_data = pd.DataFrame()
        image_data['images_paths'] = self.image_list
        f_data = self._get_feature(self.image_list)
        image_data['features'] = f_data
        image_data = image_data.dropna().reset_index(drop=True)
        image_data.to_pickle(image_data_with_features_pkl(self.model_name))
        print(f"\033[94m Image Meta Information Saved: [metadata-files/{self.model_name}/image_data_features.pkl]")
        return image_data

    def _start_indexing(self, image_data):
        self.image_data = image_data
        d = len(image_data['features'][0])  # Length of item vector that will be indexed
        self.d = d
        index = faiss.IndexFlatL2(d)
        features_matrix = np.vstack(image_data['features'].values).astype(np.float32)
        index.add(features_matrix)  # Add the features matrix to the index
        faiss.write_index(index, image_features_vectors_idx(self.model_name))
        print("\033[94m Saved The Indexed File:" + f"[metadata-files/{self.model_name}/image_features_vectors.idx]")

    def run_index(self) -> None:
        """
        Indexes the images in the image_list and creates an index file for fast similarity search.
        """
        if len(os.listdir(f'metadata-files/{self.model_name}')) == 0:
            data = self._start_feature_extraction()
            self._start_indexing(data)
        else:
            print("\033[93m Meta data already Present")
        self.image_data = pd.read_pickle(image_data_with_features_pkl(self.model_name))
        self.f = len(self.image_data['features'][0])

    def _search_by_vector(self, v, n: int) -> dict:
        self.v = v
        self.n = n
        index = faiss.read_index(image_features_vectors_idx(self.model_name))
        D, I = index.search(np.array([self.v], dtype=np.float32), self.n)
        return dict(zip(I[0], self.image_data.iloc[I[0]]['images_paths'].to_list()))

    def _get_query_vector(self, image_bytes: bytes):
        with Image.open(io.BytesIO(image_bytes)) as img:
            query_vector = self._extract(img)
            return query_vector

    def get_similar_images(self, image_bytes: bytes, number_of_images: int = 8) -> dict[Any, Any]:
        self.number_of_images = number_of_images
        query_vector = self._get_query_vector(image_bytes)
        img_dict = self._search_by_vector(query_vector, self.number_of_images)
        return img_dict
    
    def get_image_metadata_file(self):
        self.image_data = pd.read_pickle(image_data_with_features_pkl(self.model_name))
        return self.image_data