#!/bin/bash

current_dir=$(pwd)

cd $current_dir/../DeepSORT_YOLOv5_Pytorch-master
source activate transReID
python ./main.py --obtain_raw_data

cd $current_dir
source activate chatGlm
python ./test.py --config_file configs/DukeMTMC/vit_transreid_stride.yml
python ./raw_data_ReID.py

cd $current_dir/../DeepSORT_YOLOv5_Pytorch-master
source activate transReID
python ./main.py



# #!/bin/bash

# current_dir=$(pwd)
# output_dir="$current_dir/output/log"

# rm -rf $output_dir
# mkdir -p $output_dir

# cd $current_dir/../yolo-deepsort/DeepSORT_YOLOv5_Pytorch-master/DeepSORT_YOLOv5_Pytorch-master
# source activate transReID
# python ./main.py --obtain_raw_data > $output_dir/main_output.txt

# cd $current_dir
# source activate chatGlm
# python ./test.py --config_file configs/DukeMTMC/vit_transreid_stride.yml > $output_dir/test_output.txt

# python ./raw_data_ReID.py > $output_dir/raw_data_ReID_output.txt

# cd $current_dir/../yolo-deepsort/DeepSORT_YOLOv5_Pytorch-master/DeepSORT_YOLOv5_Pytorch-master
# source activate transReID
# python ./main.py > $output_dir/main_output_2.txt
