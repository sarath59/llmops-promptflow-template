#!/bin/bash

# Description: 
# This script deploys prompt flow image to Azure Web App

set -e # fail on error
env_name=${{ parameters.DEPLOY_ENVIRONMENT }}
deploy_config="./${{ parameters.flow_to_execute }}/configs/deployment_config.json"
con_object=$(jq ".webapp_endpoint[] | select(.ENV_NAME == \"$env_name\")" "$deploy_config")
REGISTRY_NAME=$(echo "$con_object" | jq -r '.REGISTRY_NAME')
rgname=$(echo "$con_object" | jq -r '.WEB_APP_RG_NAME')
udmid=$(echo "$con_object" | jq -r '.USER_MANAGED_ID')
appserviceplan=$(echo "$con_object" | jq -r '.APP_PLAN_NAME')
appserviceweb=$(echo "$con_object" | jq -r '.WEB_APP_NAME')
acr_rg=$(echo "$con_object" | jq -r '.REGISTRY_RG_NAME')
websku=$(echo "$con_object" | jq -r '.WEB_APP_SKU')

read -r -a connection_names <<< "$(echo "$con_object" | jq -r '.CONNECTION_NAMES | join(" ")')"
echo $connection_names

az group create --name $rgname --location westeurope
      
az identity create --name $udmid --resource-group $rgname
sleep 15
      
principalId=$(az identity show --resource-group $rgname \
    --name $udmid --query principalId --output tsv)
      
registryId=$(az acr show --resource-group $acr_rg \
    --name $REGISTRY_NAME --query id --output tsv)
      
az role assignment create --assignee $principalId --scope $registryId --role "AcrPull"
az appservice plan create --name $appserviceplan --resource-group $rgname --is-linux --sku $websku

az webapp create --resource-group $rgname --plan $appserviceplan --name $appserviceweb --deployment-container-image-name \
    $REGISTRY_NAME.azurecr.io/${{ parameters.flow_to_execute }}_${{ parameters.DEPLOY_ENVIRONMENT }}:$(Build.BuildNumber)

az webapp config appsettings set --resource-group $rgname --name $appserviceweb \
    --settings WEBSITES_PORT=8080

for name in "${connection_names[@]}"; do
    api_key=$(echo '${{ parameters.CONNECTION_DETAILS }}' \
        | jq -r --arg name "$name" '.[] \
        | select(.name == $name) \
        | .api_key')

    uppercase_name="${name^^}"
    modified_name="${uppercase_name}_API_KEY"
    az webapp config appsettings set \
        --resource-group $rgname \
        --name $appserviceweb \
        --settings $modified_name=$api_key
done

id=$(az identity show --resource-group $rgname --name $udmid --query id --output tsv)

az webapp identity assign --resource-group $rgname --name $appserviceweb --identities $id
 
appConfig=$(az webapp config show --resource-group $rgname --name $appserviceweb --query id --output tsv)

az resource update --ids $appConfig --set properties.acrUseManagedIdentityCreds=True

clientId=$(az identity show --resource-group $rgname --name $udmid --query clientId --output tsv)

az resource update --ids $appConfig --set properties.AcrUserManagedIdentityID=$clientId

