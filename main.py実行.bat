@echo off
if not exist ".\venv" (
  echo Python���z�����쐬���܂�
  python -m venv venv
  echo �K�{�p�b�P�[�W���C���X�g�[�����܂�
  .\venv\Scripts\python.exe -m pip install -r requirements.txt
)

.\venv\Scripts\python.exe main.py