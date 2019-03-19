import os,sys
import time
import cv2
import multiprocessing
import numpy as np
from get_image import Get_Image
import signal
import re
PORT = 23333

def get_device_no():
    r = os.popen('adb devices')
    info = r.readlines()
    device_list = []
    for line in info:
        line = line.strip('\r\n')
        if len(line)>2 and '\tdevice' in line:
            device_list.append(line.split('\t')[0])
    print('Device list: %s'%str(device_list))
    return device_list

def get_screen_shape(device_list):
    display_shape_list = []
    for device_no in device_list:
        r = os.popen('adb -s %s shell dumpsys window displays | find /i "init"'%(device_no,))
        info = r.readlines()[0]
        for s in info.split(' '):
            if 'init=' in s:
                display_shape_list.append(re.findall(r"\d+\.?\d*",s))
    print('Display shape:', display_shape_list)
    return display_shape_list

def get_config_ready():
    device_list = get_device_no()
    display_shape_list = get_screen_shape(device_list)
    # Get port list:
    port_list = [i for i in range(PORT, PORT+2*len(device_list))]
    print('Following port will be occupied %s'%str(port_list))
    # Get config list:
    config_list = []
    for idx, (device_no, display_shape) in enumerate(zip(device_list, display_shape_list)):
        config_list.append(
            {
              'device_no': device_no,
              'display_shape': display_shape,
              'device_input': Get_Image(device_no, port_list[2*idx], display_shape)
            })

    # Wait until all config finished
    time.sleep(2)
    return config_list, device_list

def process_kenerl(undecode_image):
    image = cv2.imdecode(np.array(bytearray(undecode_image)), 1)
    return image

#将各个设备的当前帧图片存入img_list
def get_image_to_mem(config_list,pool):
    undecode_image_list = []
    for config in config_list:
        undecode_image_list.append(config['device_input'].Get_Frame_for_Agent_undecode())
    results = []
    for undecode_image in undecode_image_list: #各个子进程处理当前图片
        result = pool.apply_async(process_kenerl, args=(undecode_image,))
        results.append(result)

    img_list= []
    for result in results:
        img_list.append(result.get())
    return img_list

def createVideo(video_name):
    image_path =os.path.join(os.getcwd(),video_name)
    print(image_path)
    files = os.listdir(image_path)
    image_name_list = list(filter(lambda x: '.jpg' in x, files))
    fps = 24
    # 图片数
    img_size = (480, 270)

    #视频格式
    fourcc = cv2.VideoWriter_fourcc('M', 'J', 'P', 'G')
    video_dir = os.path.join(os.getcwd(),video_name+'.avi')
    videoWriter = cv2.VideoWriter(video_dir, fourcc, fps, img_size)
    for image in image_name_list:
        frame = cv2.imread(os.path.join(image_path,image))
        videoWriter.write(frame)
    videoWriter.release()
    print('finished')


def save_image_kenerl(img, device_no, save_image_path):
    image_path = os.path.join(save_image_path,device_no,'%s.jpg' % time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime()))
    cv2.imwrite(image_path, img)

def main( save_image_path):

    device_list = get_device_no()
    num_processes = len(device_list)
    # Add following line in Windows plateform, to avoid RuntimeError
    multiprocessing.freeze_support()
    pool = multiprocessing.Pool(processes=num_processes)
    # Init opencv window
    config_list, device_list = get_config_ready()

    if not os.path.exists(save_image_path):
        os.makedirs(save_image_path)

    os.chdir(save_image_path)
    for device in device_list:
        if not os.path.exists(device):
            print('mk dir ...')
            os.makedirs(device)

    # For multi thread clear
    def Handler(sig_num, frame):
        print("EXIT!!! CLOSE CONNECTION!!")
        pool.close()
        pool.join()
        for config in config_list:
            config['device_input'].close()
        sys.exit(sig_num)
    signal.signal(signal.SIGINT, Handler)

    while True:
        img_list = get_image_to_mem(config_list, pool)  #多少个设备就有多少张图片,把每个设备的当前图片取出来
        for img, device_no in zip(img_list, device_list):
            cv2.imshow(device_no,img)
            pool.apply_async(save_image_kenerl, args=(img, device_no, save_image_path)) #将各个设备的当前帧保存起来
            print("按'b'键可以结束测试")
        if cv2.waitKey(1) & 0xFF == ord('b'):
            break

if __name__=='__main__':
    save_image_path = 'image01'
    main(save_image_path)

