echo 'english (new structure)'
ls audio_files/en/* 2>/dev/null | wc
echo 'english (old structure)'
ls audio_files/*/en/shared/* 2>/dev/null | wc
echo 'spanish -- Columbian (new structure)'
ls audio_files/es-CO/* 2>/dev/null | wc
echo 'spanish -- Columbian (old structure)'
ls audio_files/*/es-CO/shared/* 2>/dev/null | wc
echo 'german (new structure)'
ls audio_files/de/* 2>/dev/null | wc
echo 'german (old structure)'
ls audio_files/*/de/shared/* 2>/dev/null | wc