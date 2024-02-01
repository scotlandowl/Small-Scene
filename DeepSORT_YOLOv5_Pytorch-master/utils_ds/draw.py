import numpy as np
import cv2
import os
import shutil

palette = (2 ** 11 - 1, 2 ** 15 - 1, 2 ** 20 - 1)


def compute_color_for_labels(label):
    """
    Simple function that adds fixed color depending on the class
    """
    color = [int((p * (label ** 2 - label + 1)) % 255) for p in palette]
    return tuple(color)


def draw_boxes(img, bbox, identities=None, query_id=0, offset=(0,0), draw=False, colors=None, frames=25):
    m, n, _ = img.shape
    camera = 1
    cropped_images = []
    # root = '../TransReID-main/data/Small_Scenes_1/'
    root = '../../data/Small_Scenes_1/'
    reID_root = '../../reID'
    reID_root_new = '../../reID_new'
    file_path = os.path.join(reID_root, str(query_id) + '.txt')
    file_path_new = os.path.join(reID_root_new, str(query_id) + '.txt')
    
    if draw:
        for j,box in enumerate(bbox):
            x1,y1,x2,y2 = [int(i) for i in box]
            x1 += offset[0]
            x2 += offset[0]
            y1 += offset[1]
            y2 += offset[1]
            
            idx = int(identities[j]) if identities is not None else 0    
            # color = compute_color_for_labels(idx)
            # print("#", color)
            color = colors[idx]
            label = '{}{:d}'.format("", idx)
            t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 2 , 2)[0]
            cv2.rectangle(img,(x1, y1),(x2,y2),color,3)
            cv2.rectangle(img,(x1, y1),(x1+t_size[0]+3,y1+t_size[1]+4), color,-1)
            cv2.putText(img,label,(x1,y1+t_size[1]+4), cv2.FONT_HERSHEY_PLAIN, 2, [255,255,255], 2)    
            
        # with open(file_path_new, 'r') as file:
        #     for line in file: 
        #         pos_str, id_str = line.split('id:')
        #         x1, x2, y1, y2 = map(int, pos_str[5:-2].split(',')) 
        #         idx = int(id_str.strip()) 
                
        #         # idx = int(identities[i]) if identities is not None else 0    
        #         color = compute_color_for_labels(idx)
        #         # print(idx, color)
        #         label = '{}{:d}'.format("", idx)
        #         t_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_PLAIN, 2 , 2)[0]
        #         cv2.rectangle(img,(x1, y1),(x2,y2),color,3)
        #         cv2.rectangle(img,(x1, y1),(x1+t_size[0]+3,y1+t_size[1]+4), color,-1)
        #         cv2.putText(img,label,(x1,y1+t_size[1]+4), cv2.FONT_HERSHEY_PLAIN, 2, [255,255,255], 2)        
                           
    else:
        if not os.path.exists(reID_root):
            os.makedirs(reID_root)   
            
        if not os.path.exists(root):
            os.makedirs(root)  
        
        if query_id == 0 and os.path.exists(root):
            shutil.rmtree(root)
            os.makedirs(root)
        
        if query_id == 0:
            output_folder = root + 'bounding_box_test'
            # os.makedirs(root + 'bounding_box_train')
        elif query_id == 1:
            output_folder = root + 'query'
        else:
            output_folder = root + 'query_' + str(query_id - 1)
            
        with open(file_path, 'w') as file:
            
            # print("---", img.shape)
            for i,box in enumerate(bbox):
                x1,y1,x2,y2 = [int(i) for i in box]
                x1 += offset[0]
                x2 += offset[0]
                y1 += offset[1]
                y2 += offset[1]
                
                d_x, d_y = x2 - x1, y2 - y1
                x1 -= d_x // 20
                x1 = max(x1, 0)
                x2 += d_x // 20
                x2 = min(x2, n - 1)
                y1 -= d_y // 20
                y1 = max(y1, 0)
                y2 += d_y // 20
                y2 = min(y2, m - 1)
                
                x = int((x1 + x2) / 2)
                y = int((y1 + y2) / 2)
                
                cropped_img = img[y1:y2, x1:x2]
                cropped_images.append(cropped_img)

                if not os.path.exists(output_folder):
                    os.makedirs(output_folder) 
                    
                filename = '{:07d}{:04d}{:04d}_c{:d}.jpg'.format(query_id, x, y, camera)
                output_path = os.path.join(output_folder, filename)
                cv2.imwrite(output_path, cropped_img)
                line = f"pos:[{x1}, {x2}, {y1}, {y2}] id:{filename[:-7]}\n"
                file.write(line)
            
    return img





if __name__ == '__main__':
    for i in range(82):
        print(compute_color_for_labels(i))
