# ssh_file
一个只使用ssh服务进行文件传输的工具,因为有的硬件设备为了最小化将sftp服务关闭,包括其他weget等下载功能全部禁用
于是我想到直接用printf命令将文件以8进制转义追加的方式写入文件
所以只需要远程可使用printf命令即可传输文件

<img width="844" height="717" alt="image" src="https://github.com/user-attachments/assets/8117b4e0-a877-406d-893d-9b8832ad09c5" />

<img width="333" height="58" alt="image" src="https://github.com/user-attachments/assets/df89a7ff-b386-456f-a919-408bb5b9ef3f" />


