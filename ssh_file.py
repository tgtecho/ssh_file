import subprocess
import threading
import queue
import time
import os
import getpass
import sys
import platform


def transfer_interactive_python(host, port, username, local_path, remote_path, password=None):
    """
    跨平台SSH文件传输，支持Windows/Linux/macOS

    Args:
        host: SSH服务器地址
        port: SSH端口
        username: 用户名
        local_path: 本地文件路径
        remote_path: 远程文件路径
        password: SSH密码（可选）
    """
    # 检查本地文件是否存在
    if not os.path.exists(local_path):
        print(f"错误: 本地文件不存在: {local_path}")
        return False

    with open(local_path, 'rb') as f:
        file_data = f.read()

    print(f"开始传输文件: {len(file_data)} 字节")
    print(f"检测到操作系统: {platform.system()}")

    # 根据操作系统选择传输方式
    if platform.system() == "Windows":
        return transfer_windows(host, port, username, local_path, remote_path, password, file_data)
    else:
        return transfer_unix(host, port, username, local_path, remote_path, password, file_data)


def transfer_windows(host, port, username, local_path, remote_path, password, file_data):
    """
    Windows系统的SSH文件传输
    """
    # 优先尝试paramiko
    try:
        import paramiko
        print("使用paramiko进行传输...")
        return transfer_with_paramiko(host, port, username, remote_path, password, file_data)
    except ImportError:
        print("paramiko未安装，尝试其他方法...")
        pass

    # 尝试使用Windows的OpenSSH
    try:
        return transfer_with_windows_openssh(host, port, username, remote_path, password, file_data)
    except Exception as e:
        print(f"Windows OpenSSH传输失败: {e}")

    # 最后尝试基础方法
    return transfer_with_subprocess_basic(host, port, username, remote_path, file_data)


def transfer_unix(host, port, username, local_path, remote_path, password, file_data):
    """
    Unix系统（Linux/macOS）的SSH文件传输
    """
    # 如果有密码，尝试sshpass
    if password:
        try:
            result = subprocess.run(['which', 'sshpass'], capture_output=True, text=True)
            if result.returncode == 0:
                print("使用sshpass进行传输...")
                return transfer_with_sshpass(host, port, username, remote_path, password, file_data)
        except:
            pass

    # 尝试paramiko
    try:
        import paramiko
        print("使用paramiko进行传输...")
        return transfer_with_paramiko(host, port, username, remote_path, password, file_data)
    except ImportError:
        pass

    # 基础SSH方法
    return transfer_with_subprocess_basic(host, port, username, remote_path, file_data)


def transfer_with_paramiko(host, port, username, remote_path, password, file_data):
    """
    使用paramiko库进行SSH文件传输
    """
    try:
        import paramiko

        print("正在使用paramiko建立SSH连接...")

        # 创建SSH客户端
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # 连接服务器
        if password:
            ssh.connect(hostname=host, port=port, username=username, password=password, timeout=30)
        else:
            # 尝试使用密钥认证
            ssh.connect(hostname=host, port=port, username=username, timeout=30)

        print("SSH连接建立成功")

        # 清空远程文件
        ssh.exec_command(f'> {remote_path}')
        time.sleep(0.5)

        # 分块传输
        chunk_size = 800
        total_chunks = (len(file_data) + chunk_size - 1) // chunk_size

        print(f"开始分块传输，共 {total_chunks} 块")

        for i in range(0, len(file_data), chunk_size):
            chunk = file_data[i:i + chunk_size]

            # 转换为八进制转义序列
            octal_data = ''.join(f'\\{oct(b)[2:].zfill(3)}' for b in chunk)

            # 执行printf命令
            cmd = f'printf "{octal_data}" >> {remote_path}'
            stdin, stdout, stderr = ssh.exec_command(cmd)

            # 等待命令执行完成
            exit_status = stdout.channel.recv_exit_status()
            if exit_status != 0:
                error = stderr.read().decode()
                print(f"命令执行失败: {error}")

            chunk_num = i // chunk_size + 1
            if chunk_num % 100 == 0 or chunk_num == total_chunks:
                progress = (chunk_num / total_chunks) * 100
                print(f"进度: {chunk_num}/{total_chunks} ({progress:.1f}%)")

            time.sleep(0.01)  # 减少延迟

        print("传输完成，验证文件大小...")

        # 检查文件大小
        stdin, stdout, stderr = ssh.exec_command(f'wc -c < {remote_path}')
        remote_size_str = stdout.read().decode().strip()

        try:
            remote_size = int(remote_size_str)
            local_size = len(file_data)

            if remote_size == local_size:
                print(f"文件传输成功! 本地大小: {local_size}, 远程大小: {remote_size}")
                success = True
            else:
                print(f"文件大小不匹配! 本地大小: {local_size}, 远程大小: {remote_size}")
                success = False
        except ValueError:
            print(f"无法解析远程文件大小: '{remote_size_str}'，假设传输成功")
            success = True

        ssh.close()
        return success

    except Exception as e:
        print(f"paramiko传输失败: {e}")
        return False


def transfer_with_windows_openssh(host, port, username, remote_path, password, file_data):
    """
    使用Windows 10/11内置的OpenSSH客户端
    """
    try:
        print("尝试使用Windows OpenSSH...")

        # 检查OpenSSH是否可用
        result = subprocess.run(['ssh', '-V'], capture_output=True, text=True, shell=True)
        if result.returncode != 0:
            raise Exception("OpenSSH不可用")

        print("检测到OpenSSH，正在连接...")

        # 如果有密码，我们需要手动输入或使用其他方法
        if password:
            print("Windows OpenSSH需要交互式输入密码")
            print("建议安装paramiko: pip install paramiko")
            return False

        # 使用SSH密钥连接
        ssh_cmd = [
            'ssh', '-p', str(port),
            '-o', 'StrictHostKeyChecking=no',
            f'{username}@{host}'
        ]

        process = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0,
            shell=True
        )

        # 等待连接建立
        time.sleep(3)

        # 清空远程文件
        cmd = f'> {remote_path}\n'
        process.stdin.write(cmd.encode())
        process.stdin.flush()
        time.sleep(1)

        # 分块传输
        chunk_size = 500  # Windows下使用较小的块
        total_chunks = (len(file_data) + chunk_size - 1) // chunk_size

        for i in range(0, len(file_data), chunk_size):
            chunk = file_data[i:i + chunk_size]

            # 转换为八进制转义序列
            octal_data = ''.join(f'\\{oct(b)[2:].zfill(3)}' for b in chunk)

            # 发送printf命令
            cmd = f'printf "{octal_data}" >> {remote_path}\n'
            process.stdin.write(cmd.encode())
            process.stdin.flush()

            chunk_num = i // chunk_size + 1
            if chunk_num % 50 == 0 or chunk_num == total_chunks:
                progress = (chunk_num / total_chunks) * 100
                print(f"进度: {chunk_num}/{total_chunks} ({progress:.1f}%)")

            time.sleep(0.05)

        print("传输完成")

        # 退出
        process.stdin.write(b'exit\n')
        process.stdin.flush()

        try:
            process.wait(timeout=30)
            return True
        except subprocess.TimeoutExpired:
            process.kill()
            return False

    except Exception as e:
        print(f"Windows OpenSSH传输失败: {e}")
        return False


def transfer_with_sshpass(host, port, username, remote_path, password, file_data):
    """
    使用sshpass进行密码认证的文件传输（Unix系统）
    """
    try:
        ssh_cmd = [
            'sshpass', '-p', password,
            'ssh', '-p', str(port),
            '-o', 'StrictHostKeyChecking=no',
            f'{username}@{host}'
        ]

        print("正在建立SSH连接...")
        process = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0
        )

        # 等待连接建立
        time.sleep(2)

        # 清空远程文件
        cmd = f'> {remote_path}\n'
        process.stdin.write(cmd.encode())
        process.stdin.flush()
        time.sleep(0.5)

        # 分块传输
        chunk_size = 800
        total_chunks = (len(file_data) + chunk_size - 1) // chunk_size

        for i in range(0, len(file_data), chunk_size):
            chunk = file_data[i:i + chunk_size]

            # 转换为八进制转义序列
            octal_data = ''.join(f'\\{oct(b)[2:].zfill(3)}' for b in chunk)

            # 发送printf命令
            cmd = f'printf "{octal_data}" >> {remote_path}\n'
            process.stdin.write(cmd.encode())
            process.stdin.flush()

            chunk_num = i // chunk_size + 1
            if chunk_num % 100 == 0 or chunk_num == total_chunks:
                progress = (chunk_num / total_chunks) * 100
                print(f"进度: {chunk_num}/{total_chunks} ({progress:.1f}%)")

        # 退出SSH连接
        process.stdin.write(b'exit\n')
        process.stdin.flush()

        try:
            process.wait(timeout=10)
            return True
        except subprocess.TimeoutExpired:
            process.kill()
            return False

    except Exception as e:
        print(f"sshpass传输失败: {e}")
        return False


def transfer_with_subprocess_basic(host, port, username, remote_path, file_data):
    """
    基础的subprocess方法（适用于已配置SSH密钥的情况）
    """
    try:
        print("使用基础SSH连接（需要预配置SSH密钥）...")

        # 构建SSH命令
        ssh_cmd = [
            'ssh', '-p', str(port),
            '-o', 'StrictHostKeyChecking=no',
            f'{username}@{host}'
        ]

        process = subprocess.Popen(
            ssh_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=False,
            bufsize=0
        )

        # 等待连接建立
        time.sleep(3)

        # 清空远程文件
        cmd = f'> {remote_path}\n'
        process.stdin.write(cmd.encode())
        process.stdin.flush()
        time.sleep(1)

        # 分块传输
        chunk_size = 800
        total_chunks = (len(file_data) + chunk_size - 1) // chunk_size

        for i in range(0, len(file_data), chunk_size):
            chunk = file_data[i:i + chunk_size]

            # 转换为八进制转义序列
            octal_data = ''.join(f'\\{oct(b)[2:].zfill(3)}' for b in chunk)

            # 发送printf命令
            cmd = f'printf "{octal_data}" >> {remote_path}\n'
            process.stdin.write(cmd.encode())
            process.stdin.flush()

            chunk_num = i // chunk_size + 1
            if chunk_num % 100 == 0 or chunk_num == total_chunks:
                progress = (chunk_num / total_chunks) * 100
                print(f"进度: {chunk_num}/{total_chunks} ({progress:.1f}%)")

        print("传输完成")

        # 退出
        process.stdin.write(b'exit\n')
        process.stdin.flush()

        try:
            process.wait(timeout=30)
            return True
        except subprocess.TimeoutExpired:
            process.kill()
            return False

    except Exception as e:
        print(f"基础传输失败: {e}")
        return False


# 使用示例
if __name__ == "__main__":
    print("SSH文件传输工具")
    print("=" * 50)

    # 检查paramiko是否安装
    try:
        import paramiko

        print("✓ paramiko已安装")
    except ImportError:
        print("✗ paramiko未安装，建议安装: pip install paramiko")

    print("=" * 50)

    # 使用密码认证
    success = transfer_interactive_python(
        host='185.216.119.74',
        port=22,
        username='root',
        local_path='qq.png',
        remote_path='/home/1.png',
        password='a296720b7945'  # 替换为实际密码
    )

    if success:
        print("\n文件传输成功!")
    else:
        print("\n文件传输失败!")
        print("\n建议:")
        print("1. 安装paramiko: pip install paramiko")
        print("2. 检查SSH服务器连接")
        print("3. 验证用户名和密码")
