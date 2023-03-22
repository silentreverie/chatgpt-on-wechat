#port=""
while getopts "n" opt
do
    case $opt in
        n)
            echo "start with new session"
            rm -f itchat.pkl
        ;;
        ?)
        echo "未知参数"
        exit 1;;
    esac
done


dir=`pwd`
echo $dir
name=`pwd | awk -F'/' '{print $NF}'`
echo $name

ps xau|grep $name | awk '{print $2}' | xargs kill -9
rm nohup.out
touch nohup.out
nohup python3 app.py $dir& tail -f nohup.out