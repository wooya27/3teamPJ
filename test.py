import os       
  import subprocess

  def run_command(user_input):
      os.system(user_input)  # 보안 취약점

  def login(password):
      if password == "1234":  # 하드코딩
          return True
