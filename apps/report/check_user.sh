#!/bin/bash

count=0

for user in `cat /etc/passwd | grep "/bin/bash" | awk -F ':' '{print $1}'`
do
    let count=$count+1
done

count2=0

printf '['
for user in `cat /etc/passwd | grep "/bin/bash" | awk -F ':' '{print $1}'`
do
    let count2=$count2+1
    user_priv=$(sudo -l -U $user | sed -n '5,$p' | tr '\n' ' ' | sed 's/ //g')
    if [ $count2 -eq $count ];then
       printf "{\"$user\":\"$user_priv\"}"
    else
        printf "{\"$user\":\"$user_priv\"},"
    fi
done
printf ']'