#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue May  8 11:48:09 2018

@author: stangen
"""
import numpy as np
from datetime import datetime
import surface_obs.madis_example.madis_utilities as mt
import sys
from EFA.duplicate_madaus.load_data import Load_Data
import EFA.duplicate_madaus.efa_functions as ef

start_time = datetime.now()
print('start time: ',start_time)
#to run this in spyder, change this to False, to run in shell script, change to True
shell_script=False

if shell_script==False:
    ensemble_type = 'eccc'
    #mainly used for loading files-order matters for loading the file
    variables = ['T2M','ALT']  #['T2M','ALT']
    #which ob type we're getting stats for, can be more than 1 ['T2M','ALT']
    ob_types = ['ALT']
    #all obs we will have in the end- for saving the file
    allobs = ['ALT']
    #date range of ensembles used
    start_date = datetime(2013,4,1,0)
    end_date = datetime(2013,4,1,12)
    #hour increment between ensemble forecasts
    incr = 12
    
    #change for how far into the forecast to get observations, 1 is 6 hours in,
    #end_index is the last forecast hour to get obs for
    start_index = 1
    end_index = 2
    
    #if True, will load/do stats on posterior ensembles, if False, will load prior
    post=True
     
    #localization radius
    loc_rad = '1000'
    
    #inflation factor (string for loading files)
    inflation = 'none'
    
    #what kind of observations are we using? MADIS or gridded future 0-hour
    #forecast "obs", sampled at some interval?
    ob_category = 'madis'
    
    #create strings for saving file at the end
    sy = start_date.strftime('%Y')
    sm = start_date.strftime('%m')
    sd = start_date.strftime('%d')
    sh = start_date.strftime('%H')
    
    ey = end_date.strftime('%Y')
    em = end_date.strftime('%m')
    ed = end_date.strftime('%d')
    eh = end_date.strftime('%H')
    
    datestr=sy+sm+sd+sh+'-'+ey+em+ed+eh
    
elif shell_script==True:
    ensemble_type = sys.argv[1]
    variables = sys.argv[2].split(',')
    ob_types = sys.argv[3].split(',')
    allobs = sys.argv[4].split(',')
    startstr = sys.argv[5]
    start_date = datetime.strptime(startstr,'%Y%m%d%H')
    endstr = sys.argv[6]
    end_date = datetime.strptime(endstr,'%Y%m%d%H')
    incr=int(sys.argv[7])
    start_index = int(sys.argv[8])
    end_index=int(sys.argv[9])
    boolstr=sys.argv[10]
    #change string to boolean for loading prior or posterior ensembles
    if boolstr == 'true':
        post=True
    elif boolstr =='false':
        post=False     
    loc_rad = sys.argv[11]  
    inflation = sys.argv[12]
    ob_category = sys.argv[13]
    
    datestr = startstr+'-'+endstr

save_dir = '/home/disk/hot/stangen/Documents/EFA/duplicate_madaus/mse_var_output/'    
#variable string
varstr = ef.var_string(allobs)
#prior/post string
if post==True:
    prior_or_post='loc'+loc_rad
if post==False:
    prior_or_post='prior'
#last forecast hour I want to get observations for
end_hour = 6*end_index

#the dict where all the data is
ob_dict = {}
#dict for the means from the data
data_dict = {}
#dicts to store SE and variance from all obs for the time period, not just stationary ones.
SE_dict = {}
variance_dict = {}
#dicts to store SE and variance from gridded obs, and from comparison with every gridpoint.
gridob_SE_dict = {}
gridob_variance_dict = {}

#creates a datelist which increments in 12 or 24 hour chunks
dates = mt.make_datetimelist(start_date, end_date, incr)
for date in dates:
    hour = date.strftime('%H')

    #create dict for variable type
    for ob_type in ob_types:
        ob_dict[ob_type] = ob_dict.get(ob_type,{})
        data_dict[ob_type] = data_dict.get(ob_type,{})
        SE_dict[ob_type] = SE_dict.get(ob_type,{})
        variance_dict[ob_type] = variance_dict.get(ob_type,{})
        
        gridob_SE_dict[ob_type] = gridob_SE_dict.get(ob_type,{})
        gridob_variance_dict[ob_type] = gridob_variance_dict.get(ob_type,{})
        
        #Load in the ensemble data for a given initilization
        efa = Load_Data(date,ensemble_type,variables,ob_type,[ob_type])
        statecls, lats, lons, elevs = efa.load_netcdfs(post=post,ob_cat=ob_category,inf=inflation,lr=loc_rad,)
        
        #Want to interpolate ALL observations valid during a given ensemble forecast.
        #Or not, to minimize runtime of script. 1 ens, var, and forecast hour takes
        #about 1 minute to run. 
        hour_step = 6
        j = start_index
        #fh = hour_step*j
        #sfh = str(fh)
        while j <= end_index:
        #while fh <= end_hour:
            fh = j*hour_step
            sfh = str(fh)
            #print(fh)
            obs = efa.load_obs(fh)
                
            #create dictionary for forecast hour
            ob_dict[ob_type][sfh] = ob_dict[ob_type].get(sfh,{})
            data_dict[ob_type][sfh] = data_dict[ob_type].get(sfh,{})
            SE_dict[ob_type][sfh] = SE_dict[ob_type].get(sfh,[])            
            variance_dict[ob_type][sfh] = variance_dict[ob_type].get(sfh,[])
            
            #create dictionary for 00Z or 12Z
            ob_dict[ob_type][sfh][hour] = ob_dict[ob_type][sfh].get(hour,{})
            
            #Create dictionaries to hold the mean values to be calculated
            data_dict[ob_type][sfh]['station_all_mse'] = data_dict[ob_type][sfh].get('station_all_mse', np.array([]))
            data_dict[ob_type][sfh]['station_all_mean_variance'] = data_dict[ob_type][sfh].get('station_all_mean_variance', np.array([]))
            data_dict[ob_type][sfh]['station_all_error_variance'] = data_dict[ob_type][sfh].get('station_all_error_variance', np.array([]))
            data_dict[ob_type][sfh]['weight'] = data_dict[ob_type][sfh].get('weight',np.array([]))
            
            #can probably delete this
            obs_pass = []
            obs_allmaritime = []
            for ob_counter, ob in enumerate(obs):
                #this gets the observation information from the text file
                ob_info = mt.get_ob_info(ob)
                #get longitude positive-definite- ie -130 lon is 230 E
                if ob_info['lon'] < 0:
                    ob_info['lon'] = ob_info['lon'] + 360
                utctime = datetime.utcfromtimestamp(ob_info['time'])
                #find interpolated ob estimate, if it passes the terrain check.
                #the terrain check is done within the closest_points function
                interp, TorF = ef.closest_points(ob_info['lat'],ob_info['lon'],lats,lons,ob_info['elev'],
                                           elevs,utctime,statecls['validtime'].values,
                                           statecls.variables[ob_type].values,need_interp=True)            

                ob_id = ob_info['name']
                ob_value = ob_info['ob']
                
                #for stations which pass the terrain check (and were assimilated):
                if TorF == True:
                #if len(interp) > 0:
                    #calculate MSE
                    se = (np.mean(interp)-ob_value)**2
                    #calculate variance
                    hx_variance_unbiased = np.var(interp, ddof=1)

                    #only fill the dictionaries with stationary stations, so bias removal can work.
                    if ob_info['stationary'] == 0:
                    
                        #-----Added just to save obs used, to plot later-----------
                        obs_pass.append(ob)
                        
                        #create dictionary for station ID if it doesn't exist
                        ob_dict[ob_type][sfh][hour][ob_id] = ob_dict[ob_type][sfh][hour].get(ob_id,{})
                        ob_dict[ob_type][sfh][hour][ob_id]['variance_unbiased'] = ob_dict[ob_type][sfh][hour][ob_id].get('variance_unbiased',[])
                        ob_dict[ob_type][sfh][hour][ob_id]['se'] = ob_dict[ob_type][sfh][hour][ob_id].get('se',[])
                        ob_dict[ob_type][sfh][hour][ob_id]['error'] = ob_dict[ob_type][sfh][hour][ob_id].get('error',[])
                        
                        #add the data to the dictionaries
                        ob_dict[ob_type][sfh][hour][ob_id]['variance_unbiased'].append(hx_variance_unbiased)                
                        ob_dict[ob_type][sfh][hour][ob_id]['error'].append(np.mean(interp)-ob_value)
                        ob_dict[ob_type][sfh][hour][ob_id]['se'].append(se)
                        
                        #ob_counter +=1
                        #print("on observation "+str(ob_counter)+" out of "+str(len(obs)))  
                    
                    #add squared error and ensemble variance from all observations which pass terrain check
                    SE_dict[ob_type][sfh].append(se)
                    variance_dict[ob_type][sfh].append(hx_variance_unbiased)
                    obs_allmaritime.append(ob)
                                  
            print('Added stats from '+str(len(obs_pass))+' obs to stats dict')
            print('Added stats from '+str(len(obs_allmaritime))+'- including all maritime observations')
            
            #gridded observations are only available every 12 hours
            if j % 2 == 0:
                #load in the gridded observations for comparison
                grid_obs = efa.load_obs(fh,madis=False)
                
                #create dictionary for forecast hour                
                gridob_SE_dict[ob_type][sfh] = gridob_SE_dict[ob_type].get(sfh,{})
                gridob_variance_dict[ob_type][sfh] = gridob_variance_dict[ob_type].get(sfh,{})
                
                #create empty lists to append SE and variance into
                gridob_SE_dict[ob_type][sfh]['obs'] = gridob_SE_dict[ob_type][sfh].get('obs',[])
                gridob_SE_dict[ob_type][sfh]['all_gridpoints'] = gridob_SE_dict[ob_type][sfh].get('all_gridpoints',[])
                gridob_variance_dict[ob_type][sfh]['obs'] = gridob_variance_dict[ob_type][sfh].get('obs',[])
                gridob_variance_dict[ob_type][sfh]['all_gridpoints'] = gridob_variance_dict[ob_type][sfh].get('all_gridpoints',[])
                
                for ob_counter, ob in enumerate(obs):
                    #this gets the observation information from the text file
                    ob_info = mt.get_ob_info(ob)
                    #get longitude positive-definite- ie -130 lon is 230 E
                    if ob_info['lon'] < 0:
                        ob_info['lon'] = ob_info['lon'] + 360
                    utctime = datetime.utcfromtimestamp(ob_info['time'])
                    #find interpolated ob estimate, if it passes the terrain check.
                    #the terrain check is done within the closest_points function
                    interp, TorF = ef.closest_points(ob_info['lat'],ob_info['lon'],lats,lons,ob_info['elev'],
                                               elevs,utctime,statecls['validtime'].values,
                                               statecls.variables[ob_type].values,need_interp=True)
                    
                    #calculate MSE
                    se = (np.mean(interp)-ob_value)**2
                    #calculate variance
                    hx_variance_unbiased = np.var(interp, ddof=1)
                    #append SE/variance to list
                    gridob_SE_dict[ob_type][sfh]['obs'].append(se)
                    gridob_variance_dict[ob_type][sfh]['obs'].append(hx_variance_unbiased)
                    
                print('Added stats from '+str(len(obs))+' gridded obs')        
                
                #comparison with all grid points
                #access the 0 hour forecast initialized fh hours after EFA'd forecast
                anl_ens_mean, lats, lons = efa.load_ens_netcdf(fh)
                #find the ensemble mean at each grid point
                fcst_ens_mean = (statecls.variables[ob_type].values).mean(axis=-1)
                #find the squared error of each grid point                
                se = (fcst_ens_mean-anl_ens_mean)**2
                #find variance of each forecast grid point
                fcst_var = np.var(statecls.variables[ob_type].values, axis=-1, ddof=1)
                
                        
            #update the forecast hour to load the next forecast, 6 hours later
            j = j + 1
            fh = hour_step*j
            #print(fh)
            sfh = str(fh)

#now go through all the data, convert to numpy arrays, and calculate the bias, 
#mse, and mean variance for each station and forecast hour

#create list to save for creating plots
stats_list = []
for var in ob_dict:
    for f_h in ob_dict[var]:
        for h in ob_dict[var][f_h]:
            for sID in list(ob_dict[var][f_h][h].keys()):
                ob_dict[var][f_h][h][sID]['variance_unbiased'] = np.array(ob_dict[var][f_h][h][sID]['variance_unbiased'])
                ob_dict[var][f_h][h][sID]['se'] = np.array(ob_dict[var][f_h][h][sID]['se'])
                ob_dict[var][f_h][h][sID]['error'] = np.array(ob_dict[var][f_h][h][sID]['error'])
                
                #Greg's method of finding variance of error being equal to mse - bias^2
                error_var = np.var(ob_dict[var][f_h][h][sID]['error'])
                #calculate mse
                ob_dict[var][f_h][h][sID]['mse'] = np.mean(ob_dict[var][f_h][h][sID]['se'])
                #calculate mean variance (using ddof=1)
                ob_dict[var][f_h][h][sID]['mean_variance_unbiased'] = np.mean(ob_dict[var][f_h][h][sID]['variance_unbiased'])

                ob_dict[var][f_h][h][sID]['error_variance'] = error_var
                             

                data_dict[var][f_h]['station_all_mse'] = np.append(data_dict[var][f_h]['station_all_mse'],ob_dict[var][f_h][h][sID]['mse'])
                data_dict[var][f_h]['station_all_mean_variance'] = np.append(data_dict[var][f_h]['station_all_mean_variance'],ob_dict[var][f_h][h][sID]['mean_variance_unbiased'])
                data_dict[var][f_h]['station_all_error_variance'] = np.append(data_dict[var][f_h]['station_all_error_variance'],ob_dict[var][f_h][h][sID]['error_variance'])
                data_dict[var][f_h]['weight'] = np.append(data_dict[var][f_h]['weight'],len(ob_dict[var][f_h][h][sID]['se']))
                del ob_dict[var][f_h][h][sID]
                
        print('Calculating ensemble average statistics')
        data_dict[var][f_h]['average_mse'] = np.average(data_dict[var][f_h]['station_all_mse'],weights=data_dict[var][f_h]['weight'])
        data_dict[var][f_h]['average_variance'] = np.average(data_dict[var][f_h]['station_all_mean_variance'],weights=data_dict[var][f_h]['weight'])
        data_dict[var][f_h]['average_error_variance'] = np.average(data_dict[var][f_h]['station_all_error_variance'],weights=data_dict[var][f_h]['weight'])
 
        #find MSE and variance of all observations, not just stationary obs, of time period.
        SE_list = np.array(SE_dict[var][f_h])
        #SE_list_sorted = np.sort(SE_list)
        MSE = np.mean(SE_list)
        variance_list = np.array(variance_dict[var][f_h])
        #variance_list_sorted = np.sort(variance_list)
        variance = np.mean(variance_list)
        #append to the stats list each statistic and info for one ens type, variable, and forecast hour
        stats_list.append(inflation+','+prior_or_post+','+ensemble_type+','+var+','+f_h+','+str(data_dict[var][f_h]['average_mse'])+','+str(data_dict[var][f_h]['average_variance'])+','+str(data_dict[var][f_h]['average_error_variance'])+','+str(MSE)+','+str(variance)+'\n')#','+str(data_dict[var][f_h]['average_variance_hx_each_bias_removed'])+'\n')

#        SE_list_stationary = data_dict[var][f_h]['station_all_mse']
#        SE_list_stationary_sorted = np.sort(SE_list_stationary)

        
#save the stats list after all forecast hours have been appended for one variable
print('Writing statistics to .txt file')
f = open(save_dir+datestr+'_'+varstr+'.txt', 'a')
for s in stats_list:
    f.write(s)
f.close()

end_time = datetime.now()
print('end time: ',end_time)
print('total time elapsed: ',end_time-start_time)
print('Done!')

#want to save ens type, ob, forecast hour in string identifier, followed by mse, variance, and error variance

##this was to save all the stations that pass the elevation check so I could plot them. 
#f = open('/home/disk/hot/stangen/Documents/EFA/duplicate_madaus/plots/2013040106obs_allmaritime.txt','w')
#for obser in obs_allmaritime:
##for obser in obs_pass:
#    f.write(obser)
#f.close()

        
            