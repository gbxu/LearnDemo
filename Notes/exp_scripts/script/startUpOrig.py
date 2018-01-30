import MySQLdb
from time import time, sleep
import datetime
import os, sys
lib_path = os.path.abspath('../util')
sys.path.append(lib_path)
from sshcontroller import *
from createXmls import *
from datacenter import *
from dataCenterUtil import *
from InitDB import *
from nodeParser import *
from checking import *


class experi_handler():
    def __init__(self, testName, dcList, userName, password, path, debug, isAmazon, nodeFile):
        print "experiment handler initialization"
        self.nodeDict = dict()
        self.userNodeList = list()
        self.shareFolder = ""
        self.userName = userName
        self.pwd = password
        self.top_path = path
        self.isAmazon = isAmazon
        self.nodeFile = nodeFile
        self.txmud_src_path = "/home/chengli/newJava"
        self.txmud_top_path = path + "txmud"
        self.tomcat_top_path = self.txmud_top_path + "/tomcat6"
        self.tomcat_lib_path = self.tomcat_top_path + "/lib"
        self.tomcat_log_path = self.tomcat_top_path + "/logs"
        self.dcs = dcList
        self.port = 60000
        self.dcFile = ""
        self.sshList = dict() #id => ssc
        self.time = 0.0
        self.testName = testName
        self.zookeeper = None
        self.appThdCount = 0
        self.proxyThdCount = 0
        self.sshimThdCount = 0
        self.coorThdCount = 0
        self.debug = debug
        self.blueToken = 0
        self.proxyScratchpadNum = 0
        self.datawriterScratchpadNum = 0
        self.dcNum = 0
        self.wpNum = 0
        self.ssNum = 0
        self.uNum = 0
        self.timeout = 0
        self.simulateUserNum = 0
        
        self.coordinatorJar = ""
        self.storageshimJar = ""
        self.proxyJar = ""
        self.userJar = ""
        
        #some parameters for rubis
        self.backend = "mysql"

        self.rubis_root_path = "/home/chengli/newJava/src/applications/RUBiStxmud"
        self.proxy_root_path = self.rubis_root_path + "/Servlets"
        self.client_root_path = self.rubis_root_path + "/Client"
        self.txmud_outputdir = self.tomcat_lib_path + "/output/txmud"
        self.txmud_binary = self.txmud_outputdir + "/dist"
        self.client_deploy_path = self.top_path
        self.user_log_path = self.client_deploy_path + "/bench"
        #tomcat
        self.tomcatMem = "4G"
        self.websiteCode = dict()
        
        self.warmUpTime = 300000
        self.measureTime = 1800000
        self.tearDownTime = 60000
        
        self.clientJar = self.rubis_root_path + "/Client/rubis_client.jar"
        self.clientPropertiesFile = self.rubis_root_path + "/Client/rubis.properties.vasco"
        #self.clientTransitionTableFile = self.rubis_root_path + "/workload/vasco_transitions.txt"
        self.clientTransitionTableFile = self.rubis_root_path + "/workload/vasco_transitions_3.txt"

        #self.clientPropertiesFile = self.rubis_root_path + "/Client/rubis.properties"
        #self.clientTransitionTableFile = self.rubis_root_path + "/workload/transitions.txt"
        self.clientDeployedPropertiesFile = self.top_path + "/rubis.properties"
        self.clientDeployedTransitionTableFile = self.top_path + "/transitions.dat"
        
        self.webappDeployDir = self.tomcat_top_path+"/webapps"
        
    def getNodeDict(self):
        self.nodeDict = getNodeDict(self.nodeFile,self.pwd)
    
    def initiateDatacenters(self):
        print "initiate datacenters"
        self.getNodeDict()
        
        if len(self.nodeDict) < len(self.dcs):
            print "No enough nodes"
            sys.exit(-1)
        
        keys = self.nodeDict.keys()
        count = 0
        for x in self.dcs:
            self.initiateDatacenter(x)
            count = count + 1
        self.ssNum = getSshimNum(self.dcs)
        self.dcNum = getDcNum(self.dcs)
        self.wpNum = getProxyNum(self.dcs)
        self.uNum = getUserNum(self.dcs)
        print "all dc"
        self.printOut()
            
    def printOut(self):
        for x in range(0,self.dcNum):
            print "dc ", x
            dc = self.dcs[x]
            dc.printOut()
        
    def initiateDatacenter(self, dc):
        if dc.dbNum > 0:
            self.assignDatabases(dc)
        if dc.proxyNum > 0:
            self.assignWebProxies(dc)
        if dc.userNum > 0:
            self.assginUsers(dc)
    
    def assignWebProxies(self,dcObj):
        nodeList = self.nodeDict["proxy-"+str(dcObj.dcId)]
        for x in range(0, dcObj.proxyNum):
            node = nodeList.pop(0)
            dcObj.webproxies[x] = (node, self.port)
            self.port += 1
            
    def assginUsers(self, dcObj):
        nodeList = self.nodeDict["user-"+str(dcObj.dcId)]
        print dcObj.userNum, len(nodeList)
        count = 0
        while True:
            if count == dcObj.userNum:
                break
            for x in range(0,len(nodeList)):
                if count == dcObj.userNum:
                    break
                dcObj.users[count] = (nodeList[x], self.port)
                print "assign user", count
                self.port +=1
                count = count + 1
                        
    def prepareCode(self):
        #compile the client code
        command = "cd " + self.client_root_path + " && ant clean && ant"
        print command 
        os.system(command)
                
    def assignDatabases(self, dcObj):
        nodeList = self.nodeDict["database-"+str(dcObj.dcId)]
        for x in range(0, dcObj.dbNum):
            node = nodeList.pop(0)
            dcObj.databases[x] = (node, 50000)
                 
    def createConnections(self):
        print "create connections"
        command = "mkdir " + self.top_path + "; rm " + self.top_path + "/*.log; rm " + self.top_path + "/*.txt" 
        for dc in self.dcs:
            #coordinator
            dbPrefix = "db-"+str(dc.dcId)
            for k, v in dc.databases.items():
                print v[0].hostname
                self.sshList[dbPrefix+"-"+str(k)] = SSHController(v[0])
                self.sshList[dbPrefix+"-"+str(k)].open()
            proxyPrefix = "proxy-"+str(dc.dcId)
            for k,v in dc.webproxies.items():
                print v[0].hostname
                self.sshList[proxyPrefix+"-"+str(k)] = SSHController(v[0])
                self.sshList[proxyPrefix+"-"+str(k)].open()
                self.sshList[proxyPrefix+"-"+str(k)].run_command(command)
            userPrefix = "user-"+str(dc.dcId)
            for k,v in dc.users.items():
                print v[0].hostname
                self.sshList[userPrefix+"-"+str(k)] = SSHController(v[0])
                self.sshList[userPrefix+"-"+str(k)].open()
                self.sshList[userPrefix+"-"+str(k)].run_command(command)
            
    def setUpNetwork(self):
        command = "set enforce 0; iptables -F"
        for k,v in self.sshList.items():
            v.run_command(command)
        
    def clean_database(self):
        #clean database here
        for s in self.dcs:
            for x in range(0, s.dbNum):
                print "clean database here", s.dcId, x
                dbPrefix = "db-"+str(s.dcId)+"-"+str(x)
                ssc = self.sshList[dbPrefix]
                stopMySQLServer(ssc)
                resetDatabase(ssc, self.isAmazon, self.backend, self.dcNum)
                startMySQLServer(ssc)
                
    def refresh_databases(self):
        #get a timestamp
        utc_datetime = datetime.datetime.utcnow()
        utc_datetime_str = utc_datetime.strftime("%Y-%m-%d %H:%M:%S")
        print "utc timestamp we get now is ", utc_datetime_str
        for s in self.dcs:
            if s.dbNum>0:
                print "refresh database here", s.dcId, 0
                dbPrefix = "db-"+str(s.dcId)+"-"+str(0)
                ssc = self.sshList[dbPrefix]
                refreshDatabase(ssc, self.isAmazon, 33000, utc_datetime_str, 1, 7)
        print "Finishing refresh all database"
        
    def preload_databases(self):
        for s in self.dcs:
            if s.dbNum > 0:
                print "preload database here", s.dcId, 0
                dbPrefix = "db-"+str(s.dcId)+"-"+str(0)
                ssc = self.sshList[dbPrefix]
                command = " cd " + self.top_path + " && nohup java -jar preloadDB-big.jar rubis &> preloadDB.log"
                ssc.run_command(command)
        
        numOfDBReady = 0
        while numOfDBReady < len(self.dcs):
            print numOfDBReady, "size of dcs ", len(self.dcs)
            numOfDBReady = 0
            sleep(10)
            for s in self.dcs:
                if s.dbNum > 0:
                    print "checking database is ready or not", s.dcId, 0
                    dbPrefix = "db-"+str(s.dcId)+"-"+str(0)
                    ssc = self.sshList[dbPrefix]
                    returnVar = removeNewLine(ssc.remoteTailFile(self.top_path+"/preloadDB.log", 1))
                    if returnVar == "Successfully preloaded":
                        numOfDBReady = numOfDBReady + 1
                    elif returnVar == "Failed to preload":
                        print "you have problems to preload, please check"
                        sys.exit()
                    else:
                        break
                else:
                    numOfDBReady = numOfDBReady + 1
        print "Finishing preload all database"
                
    def checkAllDatabase(self):
        for s in self.dcs:
            for x in range(0, s.dbNum):
                print "check database here", s.dcId, x
                dbPrefix = "db-"+str(s.dcId)+"-"+str(x)
                ssc = self.sshList[dbPrefix]
                if checkDatabase(ssc, self.isAmazon) == True:
                    continue
                else:
                    return False
        return True
    
    def checkDatabases(self):
        while(True):
            if self.checkAllDatabase() == True:
                break
            sleep(20)
        print "all databases are started"
    
    def stop_database(self,dcId, dbId):
        dbPrefix = "db-"+str(dcId)+"-"+str(dbId)
        ssc = self.sshList[dbPrefix]
        stopMySQLServer(ssc)

            
    def compile_txmud(self, ssc):
        if self.isAmazon == False:
            command = "mkdir " + self.top_path + "; mkdir " + self.txmud_top_path
            ssc.run_command(command)
            
            print "\n ===> compile txmud"
            command = "cd " + self.txmud_src_path + " && ant clean && ant"
            ssc.run_command(command)
        else:
            print "check out code here"
            #command = "cd " + self.txmud_src_path + " && svn up --username osdi2012 --password=oej5Deec "
            #ssc.run_command(command)
            command = "cd " + self.txmud_src_path + " && ant clean && ant"
            ssc.run_command(command)
            
    def deploy_tomcat(self, ssc):
        
        print "\n ===> Downloading Tomcat6"
        
        if ssc.rexists(self.tomcat_top_path) == False:
            command = "wget -P "+self.top_path+" -c https://myming.googlecode.com/files/apache-tomcat-6.0.35.tar.gz"
            ssc.run_command(command)
        
            print "\n ===> Installing Tomcat6"
            command = "tar xzvf "+self.top_path+"apache-tomcat-6.0.35.tar.gz -C "+self.txmud_top_path+"  > /dev/null"
            ssc.run_command(command)
        
            command = "mv "+self.txmud_top_path+"/apache-tomcat-6.0.35 " + self.txmud_top_path+"/tomcat6"
            ssc.run_command(command)
            self.tune_tomcat(ssc)
        else:
            print "tomcat directory already exists"
        
    def deploy_mysql_driver(self, ssc):
        print "\n ===> downloading mysql driver"
        
        if ssc.rexists(self.tomcat_lib_path+"/mysql-connector-java-5.1.17-bin.jar") == False:
            command = "wget -P "+self.top_path+" -c http://crocket-slackbuilds.googlecode.com/files/mysql-connector-java-5.1.17.zip"
            ssc.run_command(command)
        
            print "Deploying mysql driver on tomcat lib dir "
            command = "mkdir -p " + self.tomcat_lib_path
            ssc.run_command(command)
        
            command = "cd "+self.top_path+" && unzip mysql-connector-java-5.1.17.zip "
            ssc.run_command(command)
        
            command = "cp "+self.top_path+"mysql-connector-java-5.1.17/mysql-connector-java-5.1.17-bin.jar " + self.tomcat_lib_path
            ssc.run_command(command)
        
            command = "cp "+self.top_path+"mysql-connector-java-5.1.17/mysql-connector-java-5.1.17-bin.jar /tmp"
            ssc.run_command(command)
        
            command = "rm -rf "+self.top_path+"mysql-connector-java-5.1.17"
            ssc.run_command(command)
        else:
            print "mysql driver already installed"
        
        
    def deploy_txmud_components(self, ssc):
        print "\n ===> deploy txmud components"
        command = "rm -f " + self.tomcat_lib_path + "/jsqlparser.jar " + self.tomcat_lib_path + "/netty-3.2.1.Final.jar "
        command += self.tomcat_lib_path + "/log4j-1.2.15.jar " + self.tomcat_lib_path + "/jdbctxmud.jar"
        ssc.run_command(command)
        
        command = "cp " + self.jsqlparserJar + " " + self.tomcat_lib_path
        ssc.run_command(command)
        command = "cp " + self.jdbcTxMudJar + " " + self.tomcat_lib_path
        ssc.run_command(command)
        command = "cp " + self.nettyJar + " " + self.tomcat_lib_path
        ssc.run_command(command)
        command = "cp " + self.logJar + " " + self.tomcat_lib_path
        ssc.run_command(command)
        
    def tune_tomcat(self, ssc):
        print "\n ===> Tuning tomcat server"
        command = "sed  -i \'2s/^/JAVA_OPTS=\"\$JAVA_OPTS -Xms"+self.tomcatMem+"\"/\' "+self.tomcat_top_path+"/bin/catalina.sh"
        ssc.run_command(command)
        
        command = "sed -i  \'/<Connector port=\"8080\" protocol=\"HTTP\/1\.1\"/{p;s/.*/maxThreads=\"10000\" minSpareThreads=\"200\"/;}\'  "+self.tomcat_top_path+"/conf/server.xml"
        ssc.run_command(command)
        
    def deploy_website(self, ssc):
        print "\n ===> deploy website"
        self.compile_txmud(ssc)
        self.deploy_tomcat(ssc)
        self.deploy_mysql_driver(ssc)
        #self.deploy_txmud_components(ssc)
       
    def configure_proxy(self, ssc, dcId, proxyId): 
        print "change db access url"
        s = self.dcs[dcId]
        databaseHost = s.databases[0][0].hostname
        databasePort = s.databases[0][1]
        print "change proxy to connect to database ", databaseHost, databasePort
        command = "sed -i '/datasource.url/c  \datasource.url    jdbc:mysql://"+str(databaseHost)+":"+str(databasePort)+"/rubis? \'  "+self.proxy_root_path+"/mysql.properties" 
        ssc.run_command(command)
        
        print "install website"
        command = "cd "+self.proxy_root_path + " && ant clean undeploy dist deploy -Dbackend="+self.backend+" -Dtotalproxy="+str(self.wpNum) +" -DdcCount="+str(self.dcNum)
        command += " -DdcId="+str(dcId) + " -DproxyId="+str(proxyId) + " -Ddbpool=100"
        ssc.run_command_long(command)
    
    def configure_all_proxy_websites(self):
        print "install proxy all websites"
        for s in self.dcs:
            for x in range(0,s.proxyNum):
                wpPrefix = "proxy-"+str(s.dcId) + "-" + str(x)
                ssc = self.sshList[wpPrefix]
                self.configure_proxy(ssc, s.dcId,x)
   
    def configure_all_user_websites(self):
        print "install all user websites"
        for s in self.dcs:
            for x in range(0,s.userNum):
                userPrefix = "user-"+str(s.dcId) + "-" + str(x)
                ssc = self.sshList[userPrefix]
                command = "sed -i '/workload_up_ramp_time_in_ms/c  \workload_up_ramp_time_in_ms  ="+str(self.warmUpTime) + "\' " + self.clientDeployedPropertiesFile
                command += " && " + "sed -i '/workload_session_run_time_in_ms/c  \workload_session_run_time_in_ms  ="+str(self.measureTime) + "\' " + self.clientDeployedPropertiesFile
                command += " && " + "sed -i '/workload_down_ramp_time_in_ms/c  \workload_down_ramp_time_in_ms  ="+str(self.tearDownTime) + "\' " + self.clientDeployedPropertiesFile
                #change the proxy ip
                connectDcId = int(s.userProxy[x][0])
                connectProxyId = int(s.userProxy[x][1])
                print "try to configure user ", s.dcId, x
                print "connect to ", connectDcId, connectProxyId
                wpIP = self.dcs[connectDcId].webproxies[connectProxyId][0].hostname
                command += " && sed -i '/httpd_hostname/c \httpd_hostname ="+wpIP+"\' "+self.clientDeployedPropertiesFile
                ssc.run_command(command)
                
                print "try to configure user to use the transition table " + self.clientDeployedTransitionTableFile
                command = "sed -i '/workload_transition_table/c \workload_transition_table =" + self.clientDeployedTransitionTableFile + "\' " + self.clientDeployedPropertiesFile
                ssc.run_command(command)
                
    def remove_other_webapp_deployment(self, ssc):
        print "remove all other deployment to avoid inteference"
        prefix = "tpcw"
        command = "rm -rf " + self.webappDeployDir + "/"+prefix +"*"
        ssc.run_command(command)
    
    def deploy_remote_proxies(self):
        print "\n ===> deploy proxies to remote nodes"
        for s in self.dcs:
            for x in range(0,s.proxyNum):
                wpPrefix = "proxy-"+str(s.dcId) + "-" + str(x)
                ssc = self.sshList[wpPrefix]
                self.remove_other_webapp_deployment(ssc)
                self.deploy_website(ssc)
                
    def deploy_remote_users(self):
        print "\n ===> deploy users to remote nodes"
        for s in self.dcs:
            for x in range(0,s.userNum):
                userPrefix = "user-"+str(s.dcId) + "-" + str(x)
                ssc = self.sshList[userPrefix]
                command = "rm -rf " + self.top_path + "/"+self.clientJar.split("/")[-1]
                ssc.run_command(command)
                #self.deploy_website(ssc)
                #cp two things, a rubis.properties
                #cp client jar file
                print "copy jar file  to client node", s.dcId, x
                ssc.put(self.top_path+"/"+self.clientJar.split("/")[-1],self.clientJar)
                print "copy client properties to client node", s.dcId, x
                ssc.put(self.clientDeployedPropertiesFile, self.clientPropertiesFile)
                
                print "copy client transition table to client node", s.dcId, x
                ssc.put(self.clientDeployedTransitionTableFile, self.clientTransitionTableFile)
                
                command = "mkdir " + self.top_path + "/bench"
                ssc.run_command(command)
                
        
    def start_rubisproxy(self, dcObj, wpId):
        dcId = dcObj.dcId
        wpPrefix = "proxy-" + str(dcId) +"-" +str(wpId)
        ssc = self.sshList[wpPrefix]
        command = "cd "+self.proxy_root_path + " && ant start"
        ssc.run_command(command, True)
        sleep(1)
        isDone = ssc.checkProcessAlive("java")
        if isDone:
            print "set up webproxy", dcId, wpId
            return True
        else:
            print "failed to set up webproxy", dcId, wpId
            return False
        
    def start_all_rubisproxy(self):
        print "try to start all proxies"
        for s in self.dcs:
            for x in range(0,s.proxyNum):
                isDone = self.start_rubisproxy(s, x)
                if isDone == False:
                    return False
        return True
        
    def stop_rubisproxy(self, dcId, wpId):
        proxyPrefix = "proxy-" + str(dcId)+"-" + str(wpId)
        ssc = self.sshList[proxyPrefix]
        ssc.killAllProcessesBySpecifiedPattern("tomcat")
            
    def start_user(self, dcObj, userId):
        dcId = dcObj.dcId
        ssc = self.sshList["user-"+str(dcObj.dcId)+"-"+str(userId)]
        connectDcId = int(self.dcs[dcObj.dcId].userProxy[userId][0])
        connectProxyId = int(self.dcs[dcObj.dcId].userProxy[userId][1])
        print "try to start user ", dcObj.dcId, userId
        print "connect to ", connectDcId, connectProxyId
        
        #change the user number
        command = "cd " + self.client_deploy_path + " && sed -i '/workload_number_of_clients_per_node/c \workload_number_of_clients_per_node ="+str(self.simulateUserNum)+"\' rubis.properties"
        command += " && nohup java -cp \"rubis_client.jar:./\" edu.rice.rubis.client.ClientEmulator "+ str(dcId) + " " + str(userId) + " &> user"+str(dcId)+"-"+str(userId)+".log &"
        ssc.run_command(command, True)
        
        sleep(1)
        isDone = ssc.checkProcessAlive("java")
        if isDone:
            print "set up user", dcId, userId
            return True
        else:
            print "failed to set up user", dcId, userId
            return False
        
    def start_all_users(self):
        print "try to start all users"
        for dcObj in self.dcs:
            if self.start_all_users_one_dc(dcObj) == False:
                return False
        return True
    
    def start_all_users_one_dc(self, dcObj):
        for userId in range(0, dcObj.userNum):
            if self.start_user(dcObj, userId) == False:
                return False
        return True
        
    def stop_user(self, dcId, userId):
        print "killall user ", dcId, userId
        ssc = self.sshList["user-"+str(dcId)+"-"+str(userId)]
        ssc.killAllProcessesBySpecifiedPattern("java")
        
    def check_user_ready(self): 
        for s in self.dcs:
            for x in range(0,s.userNum):
                ssc = self.sshList["user-"+str(s.dcId)+"-"+str(x)]
                checkUserFinished(ssc, self.userName)
        
    def kill_remote_process(self):
        
        print "\n ==> kill all remote process"    
        for dc in self.dcs:
            dcId = dc.dcId
            for x in range(0,dc.dbNum):
                self.stop_database(dcId, x)
            for x in range(0,dc.proxyNum):
                self.stop_rubisproxy(dcId, x)
            for x in range(0, dc.userNum):
                self.stop_user(dcId, x)
                
                
    def move_logfiles(self):                
        print "copy webproxy file"
        for dcObj in self.dcs:
            for x in range(0,dcObj.proxyNum):
                ssc = self.sshList["proxy-"+str(dcObj.dcId) + "-" + str(x)]
                logFileList = ssc.getFileList(self.tomcat_log_path)
                if logFileList<> None:
                    for logFile in logFileList:
                        ssc.get(self.tomcat_log_path+"/" + logFile, self.shareFolder +  "/"+logFile+".dcid"+str(dcObj.dcId) +".proxyid" +str(x) )
                else:
                    print "catalina.out dosen't exist ", dcObj.dcId, x
        
        print "copy user file"
        for dcObj in self.dcs:
            for x in range(0,dcObj.userNum):
                ssc = self.sshList["user-"+str(dcObj.dcId) + "-" + str(x)]
                logFileList = ssc.getUserLogFileList(self.user_log_path)
                if logFileList <>None:
                    #first compress the file and then download this file, and then uncompress
                    command = "cd "+self.user_log_path+" && tar -cvf rubis_dcId"+str(dcObj.dcId)+"_userId"+str(x)+".tar --exclude='*.jar'  --exclude='.properties' ./"
                    ssc.run_command(command)
                    tarFile = "rubis_dcId"+str(dcObj.dcId)+"_userId"+str(x)+".tar"
                    ssc.get(self.user_log_path+"/"+tarFile, self.shareFolder + "/"+tarFile)
                else:
                    print "user ", dcObj.dcId, x , "doesn't generate log files"
                        
    def check_proxies_ready(self):
        for dcObj in self.dcs:
            for x in range(0,dcObj.proxyNum):
                if checkTomcatProxyReady(self.sshList["proxy-" + str(dcObj.dcId) +"-" +str(x)], self.tomcat_log_path, dcObj.dcId, x, 'mysql') == False:
                    return False
                else:
                    continue
        return True
                
    def check_all_proxies_ready(self):
        while True:
            if self.check_proxies_ready() == True:
                return
            else:
                sleep(20)  
                
    '''
    The deploy experiment is to deploy the code to all machines
    '''
    def deploy_experiment(self):
        print "\n ===> deploy experiment"
        self.initiateDatacenters()
        self.createConnections()
        print "\n ===> prepare local code and jars"
        self.prepareCode()
            
        #copy website//TODO: here
        self.deploy_remote_proxies()
        self.deploy_remote_users()
        
        print "\n ===> experiment is deployed!"
    
    def configure_experiment(self):
        print "\n ===> configure experiment"
        self.initiateDatacenters()
        self.createConnections()
        
        self.configure_all_proxy_websites()
        self.configure_all_user_websites()
    
    def prepare_experiment(self):
        print "prepare connections"
        self.initiateDatacenters()
        self.createConnections()
 
    def cleanFiles(self):
        print "clean files"
        command = " rm " + self.top_path + "/*.log; rm " + self.top_path + "/*.txt" 
        proxyCommand = "rm " + self.tomcat_log_path + "/* "
        userCommand = "rm -rf " + self.client_deploy_path+"/*.log && rm -rf " + self.user_log_path + "/rubis_dcId*"
        for dc in self.dcs:
            proxyPrefix = "proxy-"+str(dc.dcId)
            for k,v in dc.webproxies.items():
                ssc = self.sshList[proxyPrefix+"-"+str(k)]
                ssc.run_command(proxyCommand)
            userPrefix = "user-"+str(dc.dcId)
            for k,v in dc.users.items():
                ssc = self.sshList[userPrefix+"-"+str(k)]
                ssc.run_command(userCommand)
        
    def logOut(self):
        for k,v in self.sshList.items():
            v.close()
            
    def finish_experiment(self):
        print "\n ===> finish experiment"
        self.kill_remote_process()
        self.move_logfiles()
        print "finish to copy data and clean systems"
        
    def run_test(self, folderPath,userNum):
        print "\n ===>run test now"
        self.kill_remote_process()
        self.setUpNetwork()
        self.cleanFiles()
        self.shareFolder = folderPath
        self.simulateUserNum = userNum
        
        self.clean_database()
        self.checkDatabases()
        sleep(20)
        self.preload_databases()
        self.refresh_databases()
        sleep(50)
        if self.start_all_rubisproxy():
            self.check_all_proxies_ready()
            if self.start_all_users():
                self.check_user_ready()
                self.finish_experiment()
                print "already finished the test"
                return True
        else:
            self.finish_experiment()
            print "some webproxies failed to connected to zookeeper or failed to set up, please check"
            return False
