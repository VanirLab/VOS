#Vanir Validator
import sys


import urllib
import asyncio
import os
 
from django.http import HttpResponse
from django.contrib import admin
from django.urls import include, path

def invokenmap(request):
        if 'username' in request.COOKIES:
                try:
                        value = request.COOKIES['username']
                        ses_email = request['member_id']
                
                except:
                        return HttpResponseRedirect['/?message=NO permission']
                
                else:
                        return HttpResponseRedirect('/')
                if authenticate(value, ses_mail) == True:
                        if captcha_validator(request.POST.get('g-recaptcha-response')) == False:
                                
                                return HttpResponseRedirect('/?message=Cannot validate Captcha&tags=hidden')
                        address=request.POST['ip']
                        if address =="":
                                return HttpResponseRedirect('/?message=address blank')
                        try:
                                data=request.POST['flags']
                                not_acceptable_strings = ['&&','all', ';','-p-','|','*','-iL',
                                                         '-iR','-e']
                                if any(x in address for x in not_acceptable_strings):
                                        return HttpResponseRedirect('/?message=Invalid strings at the Flag parameter')
                                if any(x in data for x in not_acceptable_strings):
                                        return HttpResponseRedirect('/?message=Invalid string at the Flag parameter')
                        except Exception:
                                data = ""
                                value = request.COOKIES['username']
                                if one_at_a_time (value) == False:
                                        muluser = value + ".txt"
                                        open(muluser, 'w').close()
                                        scanner_input = 'nmap' + data + '+address+'
                                        make_file (value, scanner_input)
                                        myprocess = subprocess.Popen(['schroot -c artful -u django --directory=/home/django/'+value+'/--"./magic.sh"'],shell=True,stdout=subprocess.PIPE, bufsize=1)
                                        scan_log (get_ip(request),address, value,scanner_input)
                                        t = threading.Thread(target=process_output, args=(myprocess,muluser,value))
                                        t.deamon = True
                                        t.setName(value)
                                        t.start()
                                        dbupdate(value, True, myprocess.pid)
                                        return HttpResponseRedirect("/result")
                                
                                else:
                                        ip = get_ip(request)
                                        objects = UserDataBase.objects.get(mail=value)
                                        return render(request,'*.html',{'name':objects.first_name,'user_ip':ip })
                        else:
                                return HttpResponseRedirect('/')
                        
                        def process_output(myprocess,muluser,value):
                                nextline = None
                                buf = ''
                                while True:
                                        out = myprocess.stdout.read(1)
                                        if out == '' and myprocess.poll() != None: break
                                        if out != '':
                                                buf += out
                                                if out == '\n':
                                                        nextline = buf
                                                        buf = ''
                                                        if not nextline: continue
                                                        line = nextline
                                                        nextline = None
                                                        with open(muluser, "a") as test_file:
                                                                line = line.encode("utf-8")
                                                                line = line + '<br>'
                                                                test_file.write(line)
                                                                test_file.close()
                                                                myprocess.stdout.close()
                                                
                                                                   

                                
                                
            
            
        
        
