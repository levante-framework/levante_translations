echo 'english (new structure)'
ls audio_files/en/* 2>nul | wc
echo 'english (old structure)'
ls audio_files/*/en/shared/* 2>nul | wc
echo 'spanish -- Columbian (new structure)'
ls audio_files/es-CO/* 2>nul | wc
echo 'spanish -- Columbian (old structure)'
ls audio_files/*/es-CO/shared/* 2>nul | wc
echo 'german (new structure)'
ls audio_files/de/* 2>nul | wc
echo 'german (old structure)'
ls audio_files/*/de/shared/* 2>nul | wc