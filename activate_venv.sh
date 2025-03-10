#!/bin/bash
echo '가상 환경을 활성화합니다...'
source "D:\HWP_HWPX_AI\.venv\bin\activate"
echo '가상 환경이 활성화되었습니다.'
echo 'Python 경로: '$VIRTUAL_ENV'/bin/python'
exec $SHELL
