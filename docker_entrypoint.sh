#!/bin/sh

set -eu

if [ -f "$HOME/.poetry/env" ]
then
    source $HOME/.poetry/env
fi

db=""

for v in "$@"
do
    if [ "$v" == "--db" ]
    then
        db="next"
    elif [ "$db" == "next" ]
    then
        db="$v"
    elif [[ "$v" == "--db="* ]]
    then
        db="${v#--db=}"
    fi
done

if ! [ "$db" == 'next' ] && ! [ -z "$db" ]
then
    poetry run alembic -x db="${db//+*:\/\//://}" upgrade head
fi

poetry run bot "$@"
