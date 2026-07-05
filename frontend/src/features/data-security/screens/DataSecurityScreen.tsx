import React from 'react'
import { Shield } from 'lucide-react'
import { useTranslation } from 'react-i18next'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { EntityTypeManagementScreen } from '@/features/data-security/screens'
import SmartProcessingTab from './SmartProcessingScreen'

const DataSecurityScreen: React.FC = () => {
  const { t } = useTranslation()

  return (
    <div>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5" />
            <span>{t('dataSecurity.dataLeakPrevention')}</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-6">
          <Tabs defaultValue="entity-types" className="w-full">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="entity-types">
                {t('dataSecurity.entityTypeTab')}
              </TabsTrigger>
              <TabsTrigger value="smart-processing">
                {t('dataSecurity.smartProcessingTab')}
              </TabsTrigger>
            </TabsList>
            <TabsContent value="entity-types" className="mt-6">
              <EntityTypeManagementScreen />
            </TabsContent>
            <TabsContent value="smart-processing" className="mt-6">
              <SmartProcessingTab />
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>
    </div>
  )
}

export default DataSecurityScreen
