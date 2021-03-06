#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jun 19 16:23:50 2018

@author: stangen
"""

import numpy as np
from netCDF4 import Dataset, num2date, date2num
from datetime import timedelta

def closest_points(ob_lat, ob_lon, lats, lons, ob_elev=None, elevs=None, ob_time=None, 
                   times=None, variable=None, k=4, need_interp=False, gen_obs=False,variance=0):
    """
    Function which uses the Haversine formula to compute the distances from one 
    observation lat/lon to each gridpoint. It finds the indices of the k closest 
    gridpoints (default 4). It then calls functions to check elevation and/or
    interpolate the ensemble to the observation location.
    
    ob_lat: latitude of the observation
    ob_lon: longitude of the observation
    lats: 1-d (masked) array of latitudes from ens netCDF file
    lons: 1-d (masked) array of longitudes from ens netCDF file
    ob_elev: required for check elevation function
    elevs: required for check elevation function
    ob_time: required for interpolate function
    times: required for interpolate function
    variable: required for interpolate, generate_obs functions   
    k = number of points to find
    need_interp: If True, call function to interpolate the ensemble 
    to the ob location/time. If False, call function to check 
    the elevation of the 4 nearest gridpoints.
    gen_obs: if need_interp == True: if False, call function to find ensemble
    estimate at the observation location and time. if True, call function to 
    generate "observations" from a grid at forecast hour 0.
    returns: output from check elevation or interpolate functions.
    """  
    #make a lat/lon array for comparison with station lat/lon
    lonarr, latarr = np.radians(np.meshgrid(lons, lats))

    R = 6371. # Radius of earth in km
    #convert degrees to radians
    ob_lat = np.radians(ob_lat)
    ob_lon = np.radians(ob_lon)
    #radian distance between points
    dlat = ob_lat-latarr
    dlon = ob_lon-lonarr
    #Haversine formula to calculate the great circle distance between ob and each lat/lon point (in km)
    a = np.sin(dlat/2)**2 + np.cos(ob_lat) * np.cos(latarr) * np.sin(dlon/2)**2
    dist = 2*R*np.arcsin(np.sqrt(a))
    #flatten the distance array to 1D
    dist_flat = dist.flatten()

    #find nearest 4 points (indices), in order from closest to farthest
    closest_4 = dist_flat.argsort(axis=None)[:k]

    #do we need to do interpolation?
    if need_interp==True:
        #4 closest distances
        distances = dist_flat[closest_4]
        #return to lat/lon gridbox indices
        closey, closex = np.unravel_index(closest_4, lonarr.shape)
        #if we are obtaining ob estimates of the ensemble, at multiple times
        #and for all ensemble members
        if gen_obs==False:
            #call function to check elevation
            TorF = check_elev(closest_4,elevs,ob_elev)
            interp = interpolate(closey,closex,distances,times,variable,ob_time)
            #return interpolated values and whether it passed or failed terrain check (True or False)
            return interp, TorF
        #If we are obtaining observations for assimilating, use the simpler
        #interpolation function
        if gen_obs==True:            
            return generate_obs(closey,closex,distances,variable,variance)
            
    #if no need to do interpolation, just call/return terrain check function
    elif need_interp==False:
        return check_elev(closest_4,elevs,ob_elev)            


def interpolate(closey, closex, distances, times, variable, ob_time):
    """
    Function which interpolates the state to the observation location for a given variable
    
    closey = 4 closest lat indices of the ensemble
    closex = 4 closest lon indices of the ensemble
    distances = distance from 4 closest gridpoints to the observation, for use in weights
    times = forecast times of the ensemble, in datetime format
    variable = ensemble values of variable (e.g. ALT, T2M, IVT): ntimes x nlats x nlons x nmems
    ob_time = observation time, in datetime format
    returns: value of ensemble interpolated to ob location.

    """
    
    spaceweights = np.zeros(distances.shape)
    if (distances < 1.0).sum() > 0:
        spaceweights[distances.argmin()] = 1
    else:
        # Here, inverse distance weighting (for simplicity)
        spaceweights = 1.0 / distances
        spaceweights /= spaceweights.sum()
    # Get weights in time
    #all the valid times in the ensemble
    valids = times
    timeweights = np.zeros(valids.shape)
    # Check if we are outside the valid time range
    if (ob_time < valids[0]) or (ob_time > valids[-1]):
        print("Interpolation is outside of time range in state!")
        return None
    # Find where we are in this list
    #index after the time of the observation
    lastdex = (valids >= ob_time).argmax()
    # If we match a particular time value, then
    # this is just an identity
    if valids[lastdex] == ob_time:
        # Just make a one at this time
        timeweights[lastdex] = 1
    else:
        # Linear interpolation
        diff  = (valids[lastdex] - valids[lastdex-1])
        #often going to be 21600 seconds
        totsec = diff.seconds
        #calculate time difference between time after and time of observation
        #the abs will make this positive definite, which is okay since
        #the difference will always be negative
        thisdiff = abs(ob_time - valids[lastdex])
        thissec = thisdiff.seconds
        # Put in appropriate weights
        timeweights[lastdex-1] = float(thissec) / totsec
        timeweights[lastdex] = 1.0 - (float(thissec)/totsec)
    # Now that we have the weights, do the interpolation
    #an ntimes x 4 x nens array
    interp = variable[:,closey,closex,:]
    # Do a dot product with the time weights
    # And with the space weights
    if len(interp.shape) == 3:
        interp = (timeweights[:,None,None] * interp).sum(axis=0)
    else:
        interp = (timeweights[:,None,None,None] * interp).sum(axis=0)

    if len(interp.shape) == 3:
        interp = (spaceweights[:,None,None] * interp).sum(axis=1)
    else:
        interp = (spaceweights[:,None] * interp).sum(axis=0)
    # Return estimate from all ensemble members
    return interp

def generate_obs(closey,closex,distances,variable,variance):
    """
    Function which returns "observations" from an ensemble. Hoping this 
    runs faster, since it's just dealing with an ensemble mean at a single time,
    a 2-d array instead of a 4-d array. 
    
    closey = 4 closest lat indices of the ensemble
    closex = 4 closest lon indices of the ensemble
    distances = distance from 4 closest gridpoints to the observation, for use in weights
    variable = ensemble mean values of variable (e.g. ALT, T2M, IVT) at each grid point
    variance = ensemble variance of ensemble at ob location
    
    returns: interpolated "observation" and the variance at the location.
    The variance is only actually used if get_variance in save_gridded_obs 
    is set to true, but the observation (ensemble mean) is always used.
    """
    
    spaceweights = np.zeros(distances.shape)
    if (distances < 1.0).sum() > 0:
        spaceweights[distances.argmin()] = 1
    else:
        # Here, inverse distance weighting (for simplicity)
        spaceweights = 1.0 / distances
        spaceweights /= spaceweights.sum()
    
    # Now that we have the weights, do the interpolation
    #a length 4 vector
    interp = variable[closey,closex]
    #multiply by the weights
    interp = sum(interp*spaceweights)
    
    interp_variance = variance[closey,closex]
    interp_variance = sum(interp_variance*spaceweights)
    return interp, interp_variance  
    

def check_elev(idx,elevs,ob_elev):
    """
    Function that takes in several variables to perform a terrain check 
    on observations- is the ens elevation of the 4 nearest gridpoints within 
    300 m of the ob elevation? 
    idx: index of 4 closest gridpoints of flattened lat/lon array
    elevs: nlat x nlon grid of elevations of the ens netCDF file
    ob_elev: elevation of the observation    
    Returns: True or False- True if passes terrain check, false if it doesn't.
    """
    #check if the 4 closest points have elevations which differ by more than 300 meters
    elev_flat = elevs.flatten()
    elev_four_closest = elev_flat[idx]
    elev_diff = abs(ob_elev-elev_four_closest)
    #print(elev_diff)
    if elev_diff.max() > 300:
        TorF = False
    else:
        TorF = True
    
    return TorF

def var_string(vrbls):
    """
    Function which takes in a list of variables and returns a string, formatted
    like var1_var2_var3, for use in saving files. Also replaces periods with dashes.
    """
    var_string = ''
    for v in vrbls[:-1]:  
        var_string = var_string+str(v).replace('.','-')+'_'
    var_string = var_string+str(vrbls[-1]).replace('.','-')
    return var_string

def var_num_string(vrbls, nums):
    """
    Function which takes in a list of variables and a list of numbers 
    (usually observation error variance) and returns a string, formatted like
    var1num1_var2num2, for use in saving files. The lists must be the 
    same length to work properly. Also replaces periods with dashes.
    """
    var_string = ''
    for i, v in enumerate(vrbls[:-1]):
        var_string = var_string+str(v)+str(nums[i]).replace('.','-')+'_'
    var_string = var_string+str(vrbls[-1])+str(nums[-1]).replace('.','-')
    return var_string

def make_netcdf(state,outfile,ob_err_var=''):
    """
    Function which creates/saves a netCDF file
    Takes in the full state array (state), the file path and file name (outfile), 
    and an optional argument (ob_err_var) for naming the newly created variables using the
    observation error variance used to run EFA. 
    """
    #tunit='seconds since 1970-01-01'
    tunit='hours since 1900-01-01'
    

    ob_err_var = str(ob_err_var).replace(',','-')
    # Write ensemble forecast to netcdf
    with Dataset(outfile,'w') as dset:
        dset.createDimension('time',None)
        dset.createDimension('lat',state.ny())
        dset.createDimension('lon',state.nx())
        dset.createDimension('ens',state.nmems())
        dset.createVariable('time','i4',('time',))
        dset.createVariable('lat',np.float32,('lat',))
        dset.createVariable('lon',np.float32,('lon'))
        dset.createVariable('ens','i4',('ens',))
        dset.variables['time'].units = tunit
        dset.variables['lat'].units = 'degrees_north'
        dset.variables['lon'].units = 'degrees_east'
        dset.variables['ens'].units = 'member_number'
        dset.variables['time'][:] = date2num(state.ensemble_times(),tunit)
        dset.variables['lat'][:] = state['lat'].values[:,0]
        dset.variables['lon'][:] = state['lon'].values[0,:]
        dset.variables['ens'][:] = state['mem'].values
        for var in state.vars():
            varstr = var+ob_err_var
            print('Writing variable {}'.format(var))
            dset.createVariable(varstr, np.float32, ('time','lat','lon','ens',))
            dset.variables[varstr].units = get_units(var)
            dset.variables[varstr][:] = state[var].values
                
def get_ob_points(left=-180,right=180,top=90,bottom=0,spacing=3):
    """
    Function which selects gridpoints for observations, based on the lat/lon
    boundaries and the spacing of the gridpoints (in deg lat/lon) at the lowest
    longitude. Causes less observation gridpoints to be selected at higher 
    latitudes than lower latitudes, since there is less distance between
    gridpoints at higher latitudes.
    
    Inputs:
        left: Western edge of box
        right: Eastern edge of box
        top: Northern edge of box
        bottom: Southern edge of box
        spacing: number of degrees apart lat/lon at equator to sample 
        observations
        
    Returns : A list of lat/lon pairs to use as observations. With the defaults,
    there are 2352 observations. Default is entire northern hemisphere.
    
    Caveats with this: linspace starts at the left edge of the box, so one
    of the observation pairs will always lie on that line of longitude for
    each row of latitudes.
    """
    
    #create list of latitudes from given box
    lats = range(bottom,top+spacing,spacing)
    #find number of longitudes, based on latitude and size of box
    nlons = (right-left)/spacing*np.cos(np.radians(lats))
    lons = []
    #find longitudes equally spaced within the box
    for n in nlons:
        lons.append(np.linspace(left,right,num=int(round(n)),endpoint=False))
        
    #generate lat/lon pairs
    latlon = []
    for i,lat in enumerate(lats):
        for lon in lons[i]:
            latlon.append([lat,lon])
            
    return latlon

def dt_str_timedelta(date,forecast_hour=0):
    """
    Converts a datetime object to year, month, day, and hour strings.
    Also contains the option to add n hours to the datetime object
    prior to the conversion to a string.
    """
    #get the 0-hour ensemble forecast, n hours after the model was initialized
    dt0 = date
    dt = dt0.replace(minute = 0, second=0, microsecond=0)
    dt = dt + timedelta(hours=forecast_hour)
    #convert back to strings
    dty = dt.strftime('%Y')
    dtm = dt.strftime('%m')
    dtd = dt.strftime('%d')
    dth = dt.strftime('%H')
    
    return dty, dtm, dtd, dth

def get_units(par):
    """
    Returns the units of the given geophysical parameter
    """
    if par in ['Z500','Z700','Z850','Z925','Z1000']: return 'meters'
    elif par in ['T500','T700','T850','T925','T1000','T2M','t2m']: return 'Kelvin'
    elif par in ['RH500','RH700','RH850','RH925','RH1000','RH2M']: return 'percent'
    elif par=='MSLP': return 'pascals'
    elif par =='ALT': return 'hPa'
    elif par[0:2] == 'QF': return 'g/kg*m/s'
    elif par[0:2] == 'D-': return 'deg'
    elif par=='CHI200': return '10$^{6}$ m$^{2}$ s$^{-1}$'
    elif par=='PRATE': return 'mm/day'
    elif par in ['PWAT','P6HR','tcw', 'TCW','IWV']: return 'mm'
    elif par == 'IVT': return 'kg/m/s'
    elif par in ['U500','V500','U700','V700','U850','V850','U925','V925', \
                 'U1000','V1000','U10M','V10M']: return 'm/s'
    elif par=='OLR': return 'W m$^{-2}$'
    else: raise IOError('Invalid field: {}'.format(par))
    
def get_r_crit():
    """
    table of critical spearman correlation values, corresponding with 
    nondirectional alpha values. Alpha values are 1 minus confidence level, e.g. 1 - 90/100 = .1
    alpha of 0.1 means probability of rejecting the null hypothesis when it is true is 0.1.
    See https://www.jstor.org/stable/1165017?seq=4#page_scan_tab_contents
    by Philip H. Ramsey, "Critical Values for Spearman's Rank Order Correlation"
    """
    r_crit = {
        20 : {
                90 : .380,
                95 : .447,
                98 : .522,
                99 : .570,
                99.5 : .612,
                99.8 : .662,
                99.9 : .693                        
                },
        50 : {
                90 : .235,
                95 : .279,
                98 : .329,
                99 : .363,
                99.5 : .393,
                99.8 : .43,
                99.9 : .456                       
                }
        }
        
    return r_crit