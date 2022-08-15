import os

path = "D:\\In2Guide_back_up_data\\IMGDATA_Cdrive\\OD3DDATA\\IMGDATA"
dirpath = os.walk(path)

for root, directories, files in dirpath:
#    print (root)
#    print (len(directories))
    for directory in directories:
        print(os.path.join(root,directory))
    #for file in files:
        #print(file)