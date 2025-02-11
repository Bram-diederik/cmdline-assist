add the service to /etc/systemd/system/
systemctrl enable <the service>
systemctrl start <the service>

Now you can login with your user credentials and direcly have a assist interface.
And you logout on exit

you can set RESTART=1 in the .env file to restart the chat on a CTRL+C
