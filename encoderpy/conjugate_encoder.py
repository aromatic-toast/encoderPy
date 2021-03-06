import numpy as np
import pandas as pd

def conjugate_encoder(X_train, y, cat_columns, prior_params, X_test = None, objective = "regression"):
  """This function encodes categorical variables by fitting a posterior distribution per each category
  to the target variable y, using a known conjugate-prior. The resulting mean(s) of each posterior distribution
  per each category are used as the encodings.
  
  Parameters
  ----------
  X_train : pd.DataFrame
          A pandas dataframe representing the training data set containing some categorical features/columns.
  X_test : pd.DataFrame
          A pandas dataframe representing the test set, containing some set of categorical features/columns. This is an optional argument.
  y : pd.Series
          A pandas series representing the target variable. If the objective is "binary", then this
          series should only contain two unique values.
  cat_columns : list
          The names of the categorical features in X_train and/or X_test.
  prior_params: dict
          A dictionary of parameters for each prior distribution assumed. For regression, this requires
          a dictionary with four keys and four values: mu, vega, alpha, beta. All must be real numbers, and must be greater than 0 
          except for mu, which can be negative. For binary classification, this requires a dictionary with two keys and two values: alpha, beta. All must be real 
          numbers and be greater than 0.
  objective : str
          A string, either "regression" or "binary" specifying the problem. Default is regression.
          For regression, a normal-inverse gamma prior + normal likelihood is assumed. For binary classification, a
          beta prior with binomial likelihood is assumed.
          
  Returns
  -------
  train_processed : pd.DataFrame
        The training set, with the categorical columns specified by the argument cat_columns
        replaced by their encodings. For regression, the encodings will return 2 columns, since the normal-inverse gamma distribution
        is two dimensional. For binary classification, the encodings will return 1 column.
  test_processed : pd.DataFrame
        The test set, with the categorical columns specified by the argument cat_columns
        replaced by the learned encodings from the training set. This is returned if X_test is not None.
        
  Examples
  -------
  >>> encodings = conjugate_encoder(
  my_train, 
  my_test, 
  my_train['y'], 
  cat_columns = ['foo'],
  prior = {alpha: 3, beta: 3},
  objective = "binary")
  
  >>> train_new = encodings[0]

  """
  
  if objective not in ['regression', 'binary']:
      raise Exception("Objective must be either regression or binary.")
  if (set(cat_columns).issubset(X_train.columns)) == False:
      raise Exception("X_train must contain cat_columns.")
  if isinstance(cat_columns, list) == False:
      raise Exception("Type of cat_columns must be a list.")
  if (isinstance(X_train, pd.DataFrame)) == False:
      raise Exception("Type of X_train must be pd.Dataframe.")
  if isinstance(y, pd.Series) == False:
      raise Exception("Type of y must be pd.Series.")

  if X_test is not None:
      if (set(cat_columns).issubset(X_test.columns)) == False:
          raise Exception("X_test must contain cat_columns.")
      if (isinstance(X_test, pd.DataFrame)) == False:
          raise Exception("X_test must be pd.Dataframe.")
      
  if objective == "regression":
      if set(prior_params.keys()).issubset(set(["mu", "alpha", "beta", "vega"])) == False:
          raise Exception("Invalid prior specification. The dictionary must include four keys for regression.")
          
      if prior_params['vega'] <= 0 or prior_params['beta'] <= 0 or prior_params['alpha'] <= 0:
          raise Exception("Invalid prior specification. Vega, alpha and beta should all be positive.")
          
          
      mu = prior_params['mu']
      alpha = prior_params['alpha']
      vega = prior_params['vega']
      beta = prior_params['beta']
      n = X_train.shape[0]
      
      if n == 1:
          raise Exception("Cannot fit encodings with only one data point.")
   
      train_processed = X_train.copy()
      
      if X_test is not None:
          test_processed = X_test.copy()
      
      for col in cat_columns:
          
          conditionals = train_processed.groupby(col)[y.name].aggregate(['mean', 'var'])
          conditionals.columns = ['encoded_mean', 'encoded_var']
          
          if conditionals['encoded_var'].isnull().any() == True:
              raise Exception("NA's fitted for expected variance. The variance of a single data point does not exist. Make sure columns specified are truly categorical.")
          
          mu_post = (vega * mu + n * conditionals['encoded_mean']) / (vega + n)
          alpha_post = alpha + n/2
          beta_post = beta + 0.5 * n * conditionals['encoded_var'] + ((n * vega) / (vega + n)) * (((conditionals['encoded_mean'] - mu)**2) / 2)
          
          all_encodings = pd.concat([mu_post, beta_post / (alpha_post - 1)], axis=1).reset_index() 
          all_encodings.columns = [col, 'encoded_mean' + "_" + col, 'encoded_var' + "_" + col]
                    
          train_processed = train_processed.merge(all_encodings, on=col, how="left")
          
          if X_test is not None:
              prior_var = beta / (alpha - 1)
              test_processed = test_processed.merge(all_encodings, on=col, how="left")
              test_processed['encoded_mean' + "_" + col] = test_processed['encoded_mean' + "_" + col].fillna(mu)
              test_processed['encoded_var' + "_" + col] = test_processed['encoded_var' + "_" + col].fillna(prior_var)
              test_processed = test_processed.drop(columns=col, axis=1)
              
          train_processed = train_processed.drop(columns=col, axis=1)
                 
  else:
      if set(prior_params.keys()).issubset(set(["alpha", "beta"])) == False:
          raise Exception("Invalid prior specification. The dictionary must include keys alpha, beta for binary classification.")
          
      if prior_params['alpha'] <= 0 or prior_params['beta'] <= 0:
          raise Exception("Invalid prior specification. alpha and beta should all be positive.")
          
      if len(set(y)) != 2:
          raise Exception("Binary classification can only have two unique values.")
          
      y = y.copy()
      if y.dtype == "object":
        y = np.where(y == y.unique()[0], 0, 1)
    
     
      alpha = prior_params['alpha']
      beta = prior_params['beta']
      n = X_train.shape[0]
   
      train_processed = X_train.copy()
      
      if X_test is not None:
          test_processed = X_test.copy()
      
      for col in cat_columns:
          
          conditionals = train_processed.groupby(col)[y.name].aggregate(['sum'])
          conditionals.columns = ['encoded_sum']
          
          alpha_post = alpha + conditionals['encoded_sum']
          beta_post = beta + n - conditionals['encoded_sum']
          posterior_mean = (alpha_post / (alpha_post + beta_post)).to_dict()
          
          train_processed.loc[:,col] = train_processed[col].map(posterior_mean)
 
          if X_test is not None:
              prior_mean = alpha/(alpha + beta)
              test_processed.loc[:,col] = test_processed[col].map(posterior_mean)
              test_processed.loc[:,col] = test_processed[col].fillna(prior_mean) 

  
  return [train_processed, test_processed] if X_test is not None else [train_processed]
  
